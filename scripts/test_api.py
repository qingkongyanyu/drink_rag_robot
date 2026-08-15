#!/usr/bin/env python3
"""API 冒烟测试脚本：验证后端所有核心接口。

用法（需先启动后端）：
    cd drink_rag_robot && python scripts/test_api.py

支持 BASE_URL 环境变量覆盖，例如 BASE_URL=http://localhost:8000
"""
import json
import os
import sys
import urllib.request

# Windows 控制台默认 GBK，统一 UTF-8 输出，避免 UnicodeEncodeError
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE = os.environ.get("BASE_URL", "http://127.0.0.1:8000")

PASS = 0
FAIL = 0


def req(method, path, body=None, timeout=90):
    url = BASE + path
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8"))
        except Exception:
            return e.code, {"detail": str(e)}


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name}  {detail}")


def main():
    print(f"=== Drink RAG Robot API 冒烟测试 → {BASE} ===\n")

    # 1. 健康检查
    print("[1] 系统状态")
    code, data = req("GET", "/api/system/health")
    check("health 返回 200", code == 200, f"code={code}")
    d = data.get("data", {})
    check("engine_ready=True", d.get("engine_ready") is True, str(d.get("engine_ready")))
    check("内置知识已加载", d.get("doc_count", 0) >= 1, str(d.get("doc_count")))

    # 2. 知识库统计
    print("\n[2] 知识库")
    code, data = req("GET", "/api/knowledge/stats")
    check("stats 返回 200", code == 200)
    check("chunk_count>0", (data.get("data") or {}).get("chunk_count", 0) > 0)
    code, data = req("GET", "/api/knowledge/docs")
    check("docs 列表返回", code == 200 and "docs" in data.get("data", {}))
    docs = data.get("data", {}).get("docs", [])
    check(f"存在内置知识文档 ({len(docs)})", len(docs) >= 1)

    # 3. 知识检索
    print("\n[3] 知识库检索")
    code, data = req("POST", "/api/knowledge/search", {"query": "可口可乐 糖尿病人", "top_k": 5})
    res = data.get("data", {})
    check("search 返回结果", code == 200 and res.get("results"), str(res.get("results")))
    if res.get("results"):
        top = res["results"][0]
        check("top1 含可口可乐相关", "可口可乐" in top.get("content", "") or "可乐" in top.get("content", ""),
              top.get("content", "")[:30])

    # 4. 对话（非流式）
    print("\n[4] 对话接口（非流式）")
    code, data = req("POST", "/api/chat", {
        "session_id": "smoke_test", "question": "可口可乐含糖量高吗？糖尿病人能喝吗？",
        "stream": False, "show_citations": True,
    }, timeout=120)
    ans = data.get("data", {})
    ok = code == 200 and bool(ans.get("answer"))
    check("chat 返回回答", ok, f"code={code} detail={data.get('detail','')}")
    if ok:
        print(f"      回答摘要：{ans['answer'][:80]}...")
        check("回答带来源引用", len(ans.get("sources", [])) > 0, f"sources={len(ans.get('sources', []))}")
        check("返回延迟字段", isinstance(ans.get("latency_ms"), int))

    # 5. 历史
    print("\n[5] 对话历史")
    code, data = req("GET", "/api/chat/history?session_id=smoke_test")
    msgs = data.get("data", [])
    check("历史包含至少2条消息", code == 200 and len(msgs) >= 2, f"len={len(msgs)}")

    # 6. 流式接口
    print("\n[6] 流式接口（SSE）")
    try:
        import urllib.request as ur
        payload = json.dumps({
            "session_id": "smoke_test", "question": "虚寒体质适合喝什么饮料？", "stream": True
        }, ensure_ascii=False).encode("utf-8")
        r = ur.Request(BASE + "/api/chat", data=payload,
                       headers={"Content-Type": "application/json"}, method="POST")
        with ur.urlopen(r, timeout=120) as resp:
            content = resp.read().decode("utf-8")
        has_meta = "event: meta" in content
        has_delta = "event: delta" in content
        has_done = "event: done" in content
        check("SSE 含 meta 事件", has_meta)
        check("SSE 含 delta 事件", has_delta)
        check("SSE 含 done 事件", has_done)
        if not has_delta:
            print(f"      SSE原始内容片段：{content[:200]}")
    except Exception as e:
        check("SSE 接口", False, str(e))

    # 7. 文档详情
    print("\n[7] 文档详情")
    if docs:
        code, data = req("GET", f"/api/knowledge/docs/{docs[0]['id']}")
        dd = data.get("data", {})
        check("detail 含 chunks", code == 200 and len(dd.get("chunks", [])) > 0, str(dd.get("chunks", []))[:40])

    # 汇总
    print(f"\n=== 测试完成：通过 {PASS}，失败 {FAIL} ===")
    sys.exit(0 if FAIL == 0 else 1)


if __name__ == "__main__":
    main()
