"""Offline API tests: standalone app, fake sessions, no settings or DB imports."""

from copy import deepcopy
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
import httpx
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.api.deps.db import get_db_session
from app.api.v1.endpoints.registry import router
from app.models.invoice import Dealer, DmsSystem, MappingConfig
from app.services.mapping import map_source_to_canonical


CONFIG = {
    "invoice_number": "billNo", "invoice_date": "billDate", "currency": "currencyCode",
    "subtotal": "subTotal", "tax_amount": "taxTotal", "total_amount": "grandTotal",
    "buyer_oem_id": "buyerCode",
    "line_items": {
        "source_field": "items", "description": "description", "quantity": "qty",
        "unit_price": "rate", "taxable_amount": "taxableValue", "tax_amount": "taxAmount",
        "line_total": "lineTotal",
    },
}
PAYLOAD = {
    "billNo": "CUSTOM-001", "billDate": "2026-10-10", "currencyCode": " inr ",
    "subTotal": "1,000.00", "taxTotal": "180.00", "grandTotal": "1180.00",
    "buyerCode": "OEM-1",
    "items": [{
        "description": "Brake rotor", "qty": "2", "rate": "500.00",
        "taxableValue": "1000.00", "taxAmount": "180.00", "lineTotal": "1180.00",
    }],
}


class FakeSession:
    def __init__(self):
        self.added = []
        self.add = MagicMock(side_effect=self.added.append)
        self.flush = AsyncMock(side_effect=self.assign_ids)
        self.commit = AsyncMock()
        self.rollback = AsyncMock()
        self.execute = AsyncMock()

    async def assign_ids(self):
        for index, row in enumerate(self.added, 1):
            row.id = index


class TestRegistry(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.app = FastAPI()
        self.app.include_router(router, prefix="/api")
        self.db = FakeSession()

        async def override_db():
            yield self.db

        self.app.dependency_overrides[get_db_session] = override_db
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app), base_url="http://test",
        )

    async def asyncTearDown(self):
        await self.client.aclose()
        self.app.dependency_overrides.clear()

    def create_body(self, **changes):
        body = {
            "name": "Custom DMS", "tier": 1, "integration_method": "API",
            "input_format": "JSON", "mapping_config": deepcopy(CONFIG),
        }
        body.update(changes)
        return body

    async def preview(self, config=None, payload=None):
        return await self.client.post("/api/dms-systems/preview", json={
            "mapping_config": CONFIG if config is None else config,
            "payload": PAYLOAD if payload is None else payload,
        })

    async def test_list_dealers(self):
        result = MagicMock()
        result.scalars.return_value.all.return_value = [
            Dealer(id=4, dealer_code="DLR-4", name="Dealer Four"),
        ]
        self.db.execute.return_value = result
        response = await self.client.get("/api/dealers")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [{"id": 4, "dealer_code": "DLR-4", "name": "Dealer Four"}])

    async def test_list_dms_active_mapping_and_unmapped(self):
        result = MagicMock()
        dms = DmsSystem(id=3, name="Mapped", integration_tier=1, integration_method="API", input_format="JSON")
        pdf = DmsSystem(id=4, name="PDF", integration_tier=3, integration_method="UPLOAD", input_format="PDF")
        mapping = MappingConfig(version=2, mapping_config=CONFIG)
        result.all.return_value = [(dms, mapping), (pdf, None)]
        self.db.execute.return_value = result
        response = await self.client.get("/api/dms-systems")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [{
            "id": 3, "name": "Mapped", "integration_tier": 1, "integration_method": "API",
            "input_format": "JSON", "active_mapping_version": 2, "active_mapping_config": CONFIG,
        }, {
            "id": 4, "name": "PDF", "integration_tier": 3, "integration_method": "UPLOAD",
            "input_format": "PDF", "active_mapping_version": None, "active_mapping_config": None,
        }])
        query = str(self.db.execute.call_args.args[0])
        for predicate in ("LEFT OUTER JOIN", "mapping_direction", "document_type", "is_active"):
            self.assertIn(predicate, query)

    async def test_create_atomic_mapping_v1(self):
        response = await self.client.post("/api/dms-systems", json=self.create_body())
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json(), {
            "id": 1, "name": "Custom DMS", "integration_tier": 1, "integration_method": "API",
            "input_format": "JSON", "active_mapping_version": 1, "active_mapping_config": CONFIG,
        })
        dms, mapping = self.db.added
        self.assertIsInstance(dms, DmsSystem)
        self.assertIsInstance(mapping, MappingConfig)
        self.assertEqual(mapping.dms_id, dms.id)
        self.assertEqual(mapping.mapping_direction, "SOURCE_TO_CANONICAL")
        self.assertEqual(mapping.document_type, "INVOICE")
        self.assertTrue(mapping.is_active)
        self.assertIsNone(mapping.target_system)
        self.assertEqual(self.db.flush.await_count, 2)
        self.db.commit.assert_awaited_once()
        self.db.rollback.assert_not_awaited()

    async def test_pdf_without_mapping_and_tier_alias(self):
        body = self.create_body(input_format="PDF", integration_method="UPLOAD")
        del body["mapping_config"]
        body["integration_tier"] = body.pop("tier")
        response = await self.client.post("/api/dms-systems", json=body)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["active_mapping_config"], {})
        self.assertEqual(response.json()["active_mapping_version"], 1)
        self.assertEqual(len(self.db.added), 2)

    async def test_csv_create(self):
        response = await self.client.post("/api/dms-systems", json=self.create_body(input_format="CSV", integration_method="UPLOAD"))
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.db.added[1].mapping_config, CONFIG)

    async def test_batch_create_profiles_with_individual_mappings(self):
        json_config = deepcopy(CONFIG)
        csv_config = deepcopy(CONFIG)
        csv_config["invoice_number"] = "InvoiceNumber"
        pdf_body = self.create_body(input_format="PDF", integration_method="UPLOAD")
        del pdf_body["mapping_config"]
        body = {"profiles": [
            self.create_body(name="Dealer DMS", input_format="JSON"),
            self.create_body(name="Dealer DMS", input_format="CSV", integration_method="UPLOAD", mapping_config=csv_config),
            self.create_body(name="Dealer DMS", input_format="EXCEL", integration_method="UPLOAD", mapping_config=CONFIG),
            pdf_body | {"name": "Dealer DMS"},
        ]}

        response = await self.client.post("/api/dms-systems/batch", json=body)

        self.assertEqual(response.status_code, 201)
        profiles = response.json()["profiles"]
        self.assertEqual([profile["input_format"] for profile in profiles], ["JSON", "CSV", "EXCEL", "PDF"])
        self.assertEqual({profile["name"] for profile in profiles}, {"Dealer DMS"})
        self.assertEqual([profile["active_mapping_config"] for profile in profiles], [json_config, csv_config, CONFIG, {}])
        self.assertEqual(len(self.db.added), 8)
        self.assertEqual(self.db.commit.await_count, 1)
        self.assertEqual(self.db.flush.await_count, 8)
        self.assertEqual(self.db.added[1].dms_id, self.db.added[0].id)
        self.assertEqual(self.db.added[3].dms_id, self.db.added[2].id)

    async def test_batch_create_rolls_back_all_profiles_on_failure(self):
        self.db.commit.side_effect = SQLAlchemyError("password=DO_NOT_LEAK")
        body = {"profiles": [
            self.create_body(name="Dealer DMS"),
            self.create_body(name="Dealer DMS", input_format="CSV", integration_method="UPLOAD"),
        ]}

        response = await self.client.post("/api/dms-systems/batch", json=body)

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json(), {"detail": "Unable to create DMS profiles and mappings."})
        self.assertEqual(len(self.db.added), 4)
        self.db.rollback.assert_awaited_once()

    async def test_batch_rejects_different_names_or_duplicate_formats(self):
        for profiles in (
            [self.create_body(name="DMS A"), self.create_body(name="DMS B", input_format="CSV", integration_method="UPLOAD")],
            [self.create_body(name="DMS A"), self.create_body(name="DMS A")],
        ):
            response = await self.client.post("/api/dms-systems/batch", json={"profiles": profiles})
            self.assertEqual(response.status_code, 422)
        self.db.add.assert_not_called()

    async def test_json_csv_require_mapping(self):
        for format_ in ("JSON", "CSV"):
            with self.subTest(format=format_):
                response = await self.client.post("/api/dms-systems", json=self.create_body(input_format=format_, mapping_config=None))
                self.assertEqual(response.status_code, 422)
        self.db.add.assert_not_called()

    async def test_invalid_create_attributes(self):
        for changes in ({"name": " "}, {"tier": 4}, {"tier": True}, {"tier": "1"},
                        {"integration_method": "SFTP"}, {"input_format": "XML"}):
            with self.subTest(changes=changes):
                response = await self.client.post("/api/dms-systems", json=self.create_body(**changes))
                self.assertEqual(response.status_code, 422)
        self.db.add.assert_not_called()

    async def test_create_rollback_on_flush_or_commit_failure(self):
        for stage in ("first_flush", "mapping_flush", "commit"):
            with self.subTest(stage=stage):
                self.db = FakeSession()
                failure = SQLAlchemyError("password=DO_NOT_LEAK")
                if stage == "first_flush":
                    self.db.flush.side_effect = failure
                elif stage == "mapping_flush":
                    async def fail_mapping_flush():
                        await self.db.assign_ids()
                        if len(self.db.added) == 2:
                            raise failure
                    self.db.flush.side_effect = fail_mapping_flush
                else:
                    self.db.commit.side_effect = failure
                response = await self.client.post("/api/dms-systems", json=self.create_body())
                self.assertEqual(response.status_code, 500)
                self.assertEqual(response.json(), {"detail": "Unable to create DMS system and mapping."})
                self.db.rollback.assert_awaited_once()
                if stage != "commit":
                    self.db.commit.assert_not_awaited()

    async def test_integrity_conflict_and_rollback_failure_sanitized(self):
        self.db.commit.side_effect = IntegrityError("SECRET SQL", {}, Exception("password=SECRET"))
        self.db.rollback.side_effect = SQLAlchemyError("token=SECRET")
        response = await self.client.post("/api/dms-systems", json=self.create_body())
        self.assertEqual(response.status_code, 409)
        self.assertNotIn("SECRET", response.text)
        self.db.rollback.assert_awaited_once()

    async def test_list_failures_sanitized(self):
        self.db.execute.side_effect = SQLAlchemyError("password=SECRET")
        for path in ("/api/dealers", "/api/dms-systems"):
            response = await self.client.get(path)
            self.assertEqual(response.status_code, 500)
            self.assertNotIn("SECRET", response.text)

    async def test_preview_billno_real_mapper_no_db_or_optional_defaults(self):
        self.app.dependency_overrides.clear()
        with patch("app.services.registry.map_source_to_canonical", wraps=map_source_to_canonical) as mapper:
            response = await self.preview()
            mapper.assert_called_once_with(PAYLOAD, CONFIG)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"canonical_candidate": {
            "invoice_number": "CUSTOM-001", "invoice_date": "2026-10-10", "currency": "INR",
            "subtotal": "1000.00", "tax_amount": "180.00", "total_amount": "1180.00",
            "buyer_oem_id": "OEM-1", "line_items": [{
                "description": "Brake rotor", "quantity": "2", "unit_price": "500.00",
                "taxable_amount": "1000.00", "tax_amount": "180.00", "line_total": "1180.00",
            }],
        }})
        self.db.execute.assert_not_awaited()

    async def test_preview_unknown_header_or_line_path(self):
        for field in ("invoice_number", "line_items[0].quantity"):
            config = deepcopy(CONFIG)
            if field == "invoice_number":
                config["invoice_number"] = "unknown.secret"
            else:
                config["line_items"]["quantity"] = "unknown.secret"
            response = await self.preview(config=config)
            self.assertEqual(response.status_code, 422)
            self.assertEqual(response.json(), {"detail": {
                "message": "Mapping preview failed.", "errors": [{
                    "field": field, "message": "Configured source path is missing or null.",
                }],
            }})
            self.assertNotIn("unknown.secret", response.text)

    async def test_preview_bad_values_sanitized(self):
        for field, key in (("invoice_date", "billDate"), ("subtotal", "subTotal")):
            payload = deepcopy(PAYLOAD)
            payload[key] = "password=SECRET https://user:pass@example.com"
            response = await self.preview(payload=payload)
            self.assertEqual(response.status_code, 422)
            self.assertEqual(response.json()["detail"]["errors"][0]["field"], field)
            self.assertNotIn("SECRET", response.text)
            self.assertNotIn("example.com", response.text)
        payload = deepcopy(PAYLOAD)
        payload["items"][0]["qty"] = "token=SECRET"
        response = await self.preview(payload=payload)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"]["errors"][0]["field"], "line_items[0].quantity")
        self.assertNotIn("SECRET", response.text)

    async def test_preview_invalid_line_structure(self):
        for lines in (None, {}, ["not an object"]):
            payload = deepcopy(PAYLOAD)
            payload["items"] = lines
            response = await self.preview(payload=payload)
            self.assertEqual(response.status_code, 422)

    async def test_mapping_allowed_fields_required_fields_and_nonempty_paths(self):
        invalid = []
        for field in CONFIG:
            config = deepcopy(CONFIG)
            del config[field]
            invalid.append(config)
        for field in CONFIG["line_items"]:
            config = deepcopy(CONFIG)
            del config["line_items"][field]
            invalid.append(config)
        for path in ("", "   ", "a..b", ".a", "a.", 123):
            config = deepcopy(CONFIG)
            config["invoice_number"] = path
            invalid.append(config)
            config = deepcopy(CONFIG)
            config["line_items"]["source_field"] = path
            invalid.append(config)
        config = deepcopy(CONFIG)
        config["unknown_header"] = "foo"
        invalid.append(config)
        config = deepcopy(CONFIG)
        config["line_items"]["unknown_line"] = "foo"
        invalid.append(config)
        for config in invalid:
            with self.subTest(config=config):
                response = await self.preview(config=config)
                self.assertEqual(response.status_code, 422)
                response = await self.client.post("/api/dms-systems", json=self.create_body(mapping_config=config))
                self.assertEqual(response.status_code, 422)
        self.db.add.assert_not_called()

    async def test_optional_fields_only_when_explicit_nested_paths(self):
        config = deepcopy(CONFIG)
        payload = deepcopy(PAYLOAD)
        config["supplier_dealer_code"] = "dealer.code"
        payload["dealer"] = {"code": "DLR-1"}
        optional = {
            "item_code": "SKU-1", "chassis_number": "VIN-1", "item_category": "VEHICLE",
            "discount_amount": "0.00", "tax_rate": "18.00",
        }
        for field, value in optional.items():
            config["line_items"][field] = f"extra.{field}"
        payload["items"][0]["extra"] = optional
        response = await self.preview(config=config, payload=payload)
        self.assertEqual(response.status_code, 200)
        candidate = response.json()["canonical_candidate"]
        self.assertEqual(candidate["supplier_dealer_code"], "DLR-1")
        for field, value in optional.items():
            self.assertEqual(candidate["line_items"][0][field], value)


if __name__ == "__main__":
    unittest.main()