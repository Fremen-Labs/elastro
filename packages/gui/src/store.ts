import { reactive } from 'vue'

export const state = reactive({
    authenticated: true,
    clusters: [] as any[],
    loadingClusters: false
})
