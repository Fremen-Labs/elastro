import { createApp } from 'vue'
import axios from 'axios'
import './style.css'
import App from './App.vue'
import router from './router'

axios.defaults.withCredentials = true

createApp(App)
    .use(router)
    .mount('#app')
