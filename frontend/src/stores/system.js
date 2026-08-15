import { defineStore } from 'pinia'
import { fetchStatus, fetchDailyStats } from '@/api/system'

export const useSystemStore = defineStore('system', {
  state: () => ({
    status: null,        // 综合状态
    daily: [],           // 按天统计
    online: false,
    loading: false
  }),
  actions: {
    async load() {
      this.loading = true
      try {
        const [st, daily] = await Promise.all([fetchStatus(), fetchDailyStats(14)])
        this.status = st.data
        this.daily = daily.data || []
        this.online = true
      } catch (e) {
        this.online = false
        console.warn('状态加载失败', e)
      } finally {
        this.loading = false
      }
    }
  }
})
