# Sistema de Faculdade (Flask + Firebase)

Aplicação web em Python (Flask) com níveis de acesso de Professor e Aluno. Professores podem lançar notas e faltas; Alunos consultam. Interface em tons de azul com amarelo e detalhes em cinza.

## Tecnologias
- Python + Flask (backend)
- Firebase Firestore (banco de dados)
- Firebase Hosting + Cloud Run (deploy recomendado)
- Tailwind CSS (estilo via CDN)

## Estrutura
- `index.html` e `style.css`: página de login estática (servida pelo Hosting ou pelo Flask em `/`).
- `main.py`: app Flask com rotas de autenticação e dashboards.
- `templates/`: Jinja templates para aluno e professor.
- `requirements.txt`: dependências Python.

## Preparar ambiente (Windows PowerShell)

1) Python 3.11+ e pip instalados.
2) Instale as dependências:

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r requirements.txt
```

3) Firebase Admin: gere credenciais de conta de serviço com acesso ao Firestore.
   - No Console Firebase: Configurações do Projeto > Contas de Serviço > Gerar nova chave privada.
   - Salve o arquivo JSON (não commit).
   - Defina a variável de ambiente para o caminho do JSON:

```powershell
$env:GOOGLE_APPLICATION_CREDENTIALS = "C:\\caminho\\para\\serviceAccount.json"
$env:FLASK_SECRET_KEY = "troque-esta-chave"
$env:MODE = "dev"   # opcional para habilitar /init-dev
```

4) Rodar localmente:

```powershell
python main.py
```

Abra http://localhost:8080 e, se desejar, acesse `http://localhost:8080/init-dev` para criar um aluno (RA `A123456`/senha `aluno123`) e um professor (RA `P654321`/senha `prof123`).

## Fluxo de uso
- Login pela página inicial (`index.html`).
- Professores são redirecionados para `/professor` e podem lançar notas e faltas.
- Alunos são redirecionados para `/aluno` e visualizam suas notas e faltas.

## Modelo de dados no Firestore
- `users/{ra}`: `{ ra, name, role: 'aluno'|'professor', password_hash }`
- `grades/{autoId}`: `{ aluno_ra, disciplina, nota, professor_ra, created_at }`
- `attendance/{autoId}`: `{ aluno_ra, disciplina, faltas, professor_ra, date }`

## Deploy recomendado (Hosting + Cloud Run)

1) Containerize o backend (exemplo simplificado):
- `Dockerfile` (opcional):

```Dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PORT=8080
CMD ["gunicorn", "-b", "0.0.0.0:8080", "main:app"]
```

2) Publique no Cloud Run (via gcloud) e obtenha a URL do serviço.

3) No Firebase Hosting, configure `firebase.json` com rewrites para encaminhar as rotas do backend ao Cloud Run:

```json
{
  "hosting": {
    "public": ".",
    "ignore": ["firebase.json", "**/.*", "**/node_modules/**"],
    "rewrites": [
      { "source": "/login", "run": { "serviceId": "sua-api", "region": "us-central1" } },
      { "source": "/logout", "run": { "serviceId": "sua-api", "region": "us-central1" } },
      { "source": "/aluno", "run": { "serviceId": "sua-api", "region": "us-central1" } },
      { "source": "/professor", "run": { "serviceId": "sua-api", "region": "us-central1" } },
      { "source": "/professor/**", "run": { "serviceId": "sua-api", "region": "us-central1" } }
    ]
  }
}
```

Assim, o Hosting serve `index.html` e `style.css`, e as rotas dinâmicas são atendidas pelo serviço Python no Cloud Run.

## Observações de segurança
- Em produção, use Firebase Authentication no front para obter ID Tokens e valide no backend (Firebase Admin) em vez de senha no servidor.
- Armazene somente hashes de senhas.
- Proteja variáveis e credenciais (Secrets Manager / Config).
- Valide inputs e trate erros adequadamente.

## Próximos passos
- Integrar Firebase Auth no front-end de login.
- Criar telas adicionais (boletim detalhado, filtros por disciplina, exportação).
- Adicionar testes automatizados.
