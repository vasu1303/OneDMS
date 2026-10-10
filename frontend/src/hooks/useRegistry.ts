import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { createDmsSystem, createDmsSystemBatch, getDealers, getDmsSystems, previewDmsMapping } from '@/services/api';

export const useDealers = () => useQuery({ queryKey: ['registry', 'dealers'], queryFn: getDealers, retry: false });
export const useDmsSystems = () => useQuery({ queryKey: ['registry', 'dms'], queryFn: getDmsSystems, retry: false });
export const useMappingPreview = () => useMutation({ mutationFn: previewDmsMapping });
export const useCreateDmsSystem = () => {
  const client = useQueryClient();
  return useMutation({
    mutationFn: createDmsSystem,
    onSuccess: () => { void client.invalidateQueries({ queryKey: ['registry', 'dms'] }); },
  });
};
export const useCreateDmsSystemBatch = () => {
  const client = useQueryClient();
  return useMutation({
    mutationFn: createDmsSystemBatch,
    onSuccess: () => { void client.invalidateQueries({ queryKey: ['registry', 'dms'] }); },
  });
};