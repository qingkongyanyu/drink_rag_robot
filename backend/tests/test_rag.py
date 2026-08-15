"""RAG 核心组件单元测试（不依赖外部模型/网络，可离线运行）。"""
import os
import sys
import unittest

# 确保可以 import backend 包
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, PROJECT_ROOT)

# 测试环境：关闭重排与查询改写，避免网络依赖
os.environ["RAG_USE_RERANKER"] = "false"
os.environ["ENABLE_QUERY_REWRITE"] = "false"

from backend.rag import chunker
from backend.rag.sparse_retriever import BM25Retriever


class TestChunker(unittest.TestCase):
    def test_split_drink_blocks(self):
        blocks = chunker.split_drink_blocks("饮料A ### 内容A\n\n饮料B ### 内容B")
        self.assertEqual(len(blocks), 2)
        self.assertIn("饮料A", blocks[0])

    def test_recursive_chunk_short(self):
        text = "短文本"
        self.assertEqual(chunker.recursive_chunk(text), ["短文本"])

    def test_recursive_chunk_long(self):
        text = "这是一个很长的句子。" * 100
        chunks = chunker.recursive_chunk(text, chunk_size=100, overlap=20)
        self.assertGreater(len(chunks), 1)
        for c in chunks:
            self.assertLessEqual(len(c), 110)  # 允许少量边界溢出

    def test_chunk_overlap_keeps_context(self):
        text = "第一段落。第二段落。第三段落。第四段落。" * 30
        chunks = chunker.recursive_chunk(text, chunk_size=60, overlap=15)
        joined = "".join(chunks)
        # 重叠保证内容不丢失（首尾拼接应覆盖原文）
        self.assertGreaterEqual(len(joined), len(text))

    def test_chunk_section(self):
        paras = chunker.chunk_section("短。", chunk_size=100)
        self.assertEqual(len(paras), 1)


class TestBM25(unittest.TestCase):
    def setUp(self):
        self.bm = BM25Retriever()
        self.corpus = [
            "可口可乐 碳酸饮料 含糖 高 糖尿病人 不宜",
            "农夫山泉 纯净水 无糖 补水 所有人群",
            "红牛 功能饮料 咖啡因 心悸 副作用",
        ]
        self.bm.build(self.corpus)

    def test_build(self):
        self.assertEqual(self.bm.size, 3)

    def test_relevant_retrieval(self):
        res = self.bm.search("糖尿病人能喝可乐吗", top_k=1)
        self.assertTrue(res)
        self.assertEqual(res[0]["idx"], 0)  # 应召回可乐

    def test_empty_query(self):
        self.assertEqual(self.bm.search("", top_k=3), [])
        self.assertEqual(self.bm.search("？？？", top_k=3), [])

    def test_top_k_limit(self):
        res = self.bm.search("饮料", top_k=2)
        self.assertLessEqual(len(res), 2)

    def test_rebuild(self):
        self.bm.build(["新语料A", "新语料B"])
        self.assertEqual(self.bm.size, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
