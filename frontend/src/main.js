import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './styles/base.css'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')

// 主题初始化（跟随本地存储）
const saved = localStorage.getItem('drink_theme')
document.documentElement.setAttribute('data-theme', saved || 'dark')
