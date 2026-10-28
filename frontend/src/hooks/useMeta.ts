import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";

export function useMeta() {
  return useQuery({ queryKey: ["meta"], queryFn: api.meta, staleTime: 5 * 60_000, retry: 1 });
}
