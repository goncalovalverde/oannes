import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type Granularity = 'day' | 'week' | 'biweek' | 'month'

interface FilterState {
  activeProjectId: number | null
  weeks: number
  itemType: string
  granularity: Granularity
  setActiveProject: (id: number) => void
  setWeeks: (w: number) => void
  setItemType: (t: string) => void
  setGranularity: (g: Granularity) => void
}

export const useFilterStore = create<FilterState>()(
  persist(
    (set) => ({
      activeProjectId: null,
      weeks: 12,
      itemType: 'all',
      granularity: 'week',
      setActiveProject: (id) => set({ activeProjectId: id, itemType: 'all' }),
      setWeeks: (weeks) => set({ weeks }),
      setItemType: (itemType) => set({ itemType }),
      setGranularity: (granularity) => set({ granularity }),
    }),
    { name: 'oannes-filters' },
  ),
)
