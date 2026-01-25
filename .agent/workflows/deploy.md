---
description: Deploy Elastique to production (Vercel + Cloud Run)
---

# Deployment Workflow

## Prerequisites
- gcloud CLI configured with `elastique-crm-prod` project
- Vercel CLI installed and linked to `elastique-crm` project

## Frontend (Vercel)
// turbo
```powershell
cd "d:\Homebrew Apps\Elastique - Chatbot_Text\member_dashboard"
vercel --prod
```

## Backend (Cloud Run)
```powershell
cd "d:\Homebrew Apps\Elastique - Chatbot_Text"
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
gcloud run deploy elastique-backend --source . --region us-central1 --allow-unauthenticated --project elastique-crm-prod
```

## Live URLs
- **Frontend**: https://elastique-crm.vercel.app
- **Backend**: https://elastique-backend-ielifwihkq-uc.a.run.app
- **Health Check**: https://elastique-backend-ielifwihkq-uc.a.run.app/health

## Environment Variables
### Vercel (Frontend)
- `NEXT_PUBLIC_BACKEND_URL` = `https://elastique-backend-ielifwihkq-uc.a.run.app`

### Cloud Run (Backend)
- Add via: `gcloud run services update elastique-backend --set-env-vars="KEY=VALUE" --region us-central1 --project elastique-crm-prod`
- Required for AI features: `GOOGLE_API_KEY`
