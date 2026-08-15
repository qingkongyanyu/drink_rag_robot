import { defineStore } from 'pinia'
import { fetchDocs, fetchKnowledgeStats, deleteDoc, uploadFiles } from '@/api/knowledge'

export const useKnowledgeStore = defineStore('knowledge', {
  state: () => ({
    docs: [],
    totalChunks: 0,
    stats: null,
    loading: false,
    uploading: false
  }),
  getters: {
    totalDocs: (s) => s.docs.length
  },
  actions: {
    async load() {
      this.loading = true
      try {
        const [docRes, statRes] = await Promise.all([fetchDocs(), fetchKnowledgeStats()])
        this.docs = docRes.data.docs || []
        this.totalChunks = docRes.data.total_chunks || 0
        this.stats = statRes.data || null
      } catch (e) {
        console.warn('加载知识库失败', e)
      } finally {
        this.loading = false
      }
    },
    async upload(files, category) {
      this.uploading = true
      try {
        const res = await uploadFiles(files, category)
        await this.load()
        return res
      } finally {
        this.uploading = false
      }
    },
    async remove(docId) {
      await deleteDoc(docId)
      this.docs = this.docs.filter((d) => d.id !== docId)
      await this.load()
    }
  }
})
