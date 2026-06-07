# Submission Package Guide

Create `TEAMNAME_FinalProject.zip` with this layout:

```text
TEAMNAME_FinalProject/
├── README.md                 # Setup and run (copy from repo root)
├── code/
│   ├── code_Layer1_2_WebUI_n8n/
│   ├── code_RAG_Service/
│   ├── code_Image_Analyser/
│   ├── code_Guardrails_Service/
│   ├── code_LangGraph_Agent/
│   ├── code_LLM_Service/
│   ├── code_Frontend_UI/
│   ├── code_Property_Triage/
│   ├── docker-compose.yml
│   └── tests/
├── docs/
│   ├── DEPLOYMENT.md
│   ├── INTEGRATION.md
│   ├── prompt_engineering_log_ollama.md          # Surface 5
│   ├── prompt_engineering_log_n8n_extractor.md   # Surface 1
│   ├── prompt_engineering_log_n8n_agent.md       # Surface 2
│   ├── prompt_engineering_log_rag.md             # Surface 3
│   └── prompt_engineering_log_guardrails.md      # Surface 4
└── demo/
    └── README.md               # Video link or demo.mp4
```

## Grading checklist

- [x] n8n flow JSON (`property_triage_workflow.json`) — 8+ nodes, guardrails, router
- [x] Four EC2 services (RAG, Image, Guardrails, LangGraph) + Dockerfiles
- [x] ChromaDB populate script (`code_RAG_Service/populate_index.py`, 24 listings)
- [x] PyTorch training script + `model.pth` built in Docker
- [x] WebUI with Ollama chat + n8n submission form
- [x] Five prompt engineering logs (5 iterations each)
- [ ] Architecture diagram (add `docs/architecture.png` — export from course diagram with your ports)
- [ ] Demo video 5–8 min (record per `demo/README.md`)

## Build ZIP (PowerShell)

```powershell
$team = "TEAMNAME"
$root = "C:\Users\rema7\Desktop\AI_Property_Triage_Project"
$out = "$env:TEMP\${team}_FinalProject"
Remove-Item $out -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path "$out\code","$out\docs","$out\demo" | Out-Null
Copy-Item "$root\README.md" $out
Copy-Item "$root\docker-compose.yml","$root\INTEGRATION.md" "$out\code\"
Copy-Item "$root\code_*" "$out\code\" -Recurse
Copy-Item "$root\tests" "$out\code\" -Recurse
Copy-Item "$root\docs\*.md" "$out\docs\"
Copy-Item "$root\demo\*" "$out\demo\" -Recurse -ErrorAction SilentlyContinue
Compress-Archive -Path $out -DestinationPath "$env:USERPROFILE\Desktop\${team}_FinalProject.zip"
```
