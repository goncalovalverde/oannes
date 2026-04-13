import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface FilterState {
  activeProjectId: number | null
  weeks: number
  itemType: string
  setActiveProject: (id: number) => void
  setWeeks: (w: number) => void
  setItemType: (t: string) => void
}

export const useFilterStore = create<FilterState>()(
  persist(
    (set) => ({
      activeProjectId: null,
      weeks: 12,
      itemType: 'all',
      setActiveProject: (id) => set({ activeProjectId: id, itemType: 'all' }),
      setWeeks: (weeks) => set({ weeks }),
      setItemType: (itemType) => set({ itemType }),
    }),
    { name: 'oannes-filters' },
  ),
)
