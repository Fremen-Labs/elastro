import { createApp } from 'vue'
import axios from 'axios'
import './style.css'
import App from './App.vue'
import router from './router'
import { state } from './store'

axios.defaults.withCredentials = true

axios.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response?.status === 401) {
            state.authenticated = false
        }
        return Promise.reject(error)
    },
)

createApp(App)
    .use(router)
    .mount('#app')
