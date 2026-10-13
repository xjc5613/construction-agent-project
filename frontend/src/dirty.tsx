import { createContext, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

type DirtyRegistryValue = {
  dirty: boolean;
  setDirty: (id: string, value: boolean) => void;
  confirmDiscard: () => boolean;
};

const DirtyRegistry = createContext<DirtyRegistryValue | null>(null);

export function DirtyRegistryProvider({ children }: { children: ReactNode }) {
  const [ids, setIds] = useState<Set<string>>(new Set());
  const idsRef = useRef<Set<string>>(new Set());
  const setDirty = (id: string, value: boolean) => {
    const next = new Set(idsRef.current); value ? next.add(id) : next.delete(id);
    idsRef.current = next; setIds(next);
  };
  useEffect(() => {
    const beforeUnload = (event: BeforeUnloadEvent) => {
      if (!ids.size) return;
      event.preventDefault(); event.returnValue = "";
    };
    window.addEventListener("beforeunload", beforeUnload);
    return () => window.removeEventListener("beforeunload", beforeUnload);
  }, [ids.size]);
  const value = useMemo<DirtyRegistryValue>(() => ({
    dirty: ids.size > 0, setDirty,
    confirmDiscard: () => !idsRef.current.size || window.confirm("当前页面有未保存修改，确定放弃并离开吗？"),
  }), [ids]);
  return <DirtyRegistry.Provider value={value}>{children}</DirtyRegistry.Provider>;
}

export function useDirtyRegistry() {
  const value = useContext(DirtyRegistry);
  if (!value) throw new Error("DirtyRegistryProvider is missing");
  return value;
}

export function useDirtyForm(id: string, dirty: boolean) {
  const registry = useDirtyRegistry();
  useEffect(() => {
    registry.setDirty(id, dirty);
    return () => registry.setDirty(id, false);
  }, [id, dirty]);
}
