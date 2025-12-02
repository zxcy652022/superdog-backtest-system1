===== 00_WORKFLOW.md 開始 =====

SuperDog 系統開發流程（v0.1）

⸻

	1.	新模組開發流程

⸻

Step 1：需求釐清（你 ↔ GPT）
Step 2：撰寫 spec（放進 spec/*.md）
Step 3：Claude 實作
Step 4：你本地測試
Step 5：通過後 commit

⸻

	2.	Git Flow（簡化）

⸻

分支：
	•	main：穩定可跑
	•	dev：開發主線
	•	feature/*：功能分支

流程：
	1.	git checkout -b feature/data-v0.1
	2.	完成功能後：
	•	git checkout dev
	•	git merge feature/data-v0.1
	3.	測試無誤：
	•	git checkout main
	•	git merge dev
	4.	git tag v0.1-data

⸻

	3.	Debug 流程

⸻

問題類型：
	1.	Bug（Claude 修）
	2.	規格問題（GPT 重寫 spec）
	3.	設計問題（記錄到 TODO / DECISIONS）

⸻

	4.	文件更新時機

⸻

	•	完成模組 → 記錄到 TODO / CHANGELOG
	•	大改動 → 更新 spec
	•	設計決策 → DECISIONS.md
	•	技術與知識 → NotebookLM

===== 00_WORKFLOW.md 結束 =====
