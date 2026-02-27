import { reactive } from 'vue'

export const state = reactive({
    token: null as string | null,
    clusters: [] as any[],
    loadingClusters: false
})
