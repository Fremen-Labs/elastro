import { createRouter, createWebHashHistory } from 'vue-router'
import Dashboard from '../views/Dashboard.vue'
import Settings from '../views/Settings.vue'
import Documentation from '../views/Documentation.vue'
import ClusterDetail from '../views/ClusterDetail.vue'

const routes = [
    {
        path: '/',
        name: 'Dashboard',
        component: Dashboard
    },
    {
        path: '/cluster/:name',
        name: 'ClusterDetail',
        component: ClusterDetail
    },
    {
        path: '/docs',
        name: 'Documentation',
        component: Documentation
    },
    {
        path: '/settings',
        name: 'Settings',
        component: Settings
    }
]

const router = createRouter({
    history: createWebHashHistory(), // Using hash history since we'll serve statically from Python
    routes
})

export default router
