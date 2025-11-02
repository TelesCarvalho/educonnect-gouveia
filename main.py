import os
from datetime import datetime

from flask import Flask, request, redirect, url_for, render_template, session, flash, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash

# Firebase Admin / Firestore
import firebase_admin
from firebase_admin import credentials, firestore


def create_app():
	app = Flask(__name__, static_folder='static', template_folder='templates')
	app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-me')

	# Inicializa Firebase Admin (produção ou emulador)
	if not firebase_admin._apps:
		try:
			# Se estiver usando o Firestore Emulator, inicialize sem credenciais, mas com projectId
			if os.getenv('FIRESTORE_EMULATOR_HOST'):
				project_id = (
					os.getenv('GOOGLE_CLOUD_PROJECT')
					or os.getenv('GCLOUD_PROJECT')
					or 'demo-faculdade'
				)
				firebase_admin.initialize_app(options={"projectId": project_id})
			else:
				cred_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
				if cred_path and os.path.exists(cred_path):
					cred = credentials.Certificate(cred_path)
					firebase_admin.initialize_app(cred)
				else:
					# Tenta credenciais padrão (útil no Cloud Run ou local com gcloud auth)
					firebase_admin.initialize_app()
		except Exception as e:
			# Deixa claro no log, mas não quebra a criação do app para permitir mensagens úteis em runtime
			print(f"[ERRO] Falha ao inicializar Firebase Admin: {e}")
			raise

	app.db = firestore.client()

	# ---------------------- Utilitários ----------------------
	def get_user(ra: str):
		if not ra:
			return None
		doc_ref = app.db.collection('users').document(ra)
		doc = doc_ref.get()
		return doc.to_dict() if doc.exists else None

	def login_required(role: str | None = None):
		def decorator(func):
			from functools import wraps

			@wraps(func)
			def wrapper(*args, **kwargs):
				user = session.get('user')
				if not user:
					flash('Faça login para continuar.', 'warning')
					return redirect(url_for('home'))
				if role and user.get('role') != role:
					flash('Acesso negado para este perfil.', 'error')
					return redirect(url_for('home'))
				return func(*args, **kwargs)

			return wrapper
		return decorator

	# ---------------------- Rotas Públicas ----------------------
	@app.route('/')
	def home():
		"""Serve o index.html estático existente (página de login)."""
		# Mantém compatibilidade com o arquivo já no diretório raiz
		return send_from_directory('.', 'index.html')

	@app.route('/style.css')
	def style_css():
		return send_from_directory('.', 'style.css')

	@app.post('/login')
	def login():
		ra = request.form.get('ra', '').strip()
		senha = request.form.get('senha', '')

		user = get_user(ra)
		if not user:
			flash('Usuário não encontrado.', 'error')
			return redirect(url_for('home'))

		senha_hash = user.get('password_hash')
		if not senha_hash or not check_password_hash(senha_hash, senha):
			flash('Senha inválida.', 'error')
			return redirect(url_for('home'))

		# Login OK
		session['user'] = {
			'ra': ra,
			'name': user.get('name'),
			'role': user.get('role'),  # 'aluno' ou 'professor'
		}

		if user.get('role') == 'professor':
			return redirect(url_for('professor_dashboard'))
		return redirect(url_for('aluno_dashboard'))

	@app.get('/logout')
	def logout():
		session.clear()
		flash('Sessão encerrada.', 'info')
		return redirect(url_for('home'))

	# ---------------------- Rotas Aluno ----------------------
	@app.get('/aluno')
	@login_required(role=None)  # tanto aluno quanto professor podem ver, mas exibiremos conforme role
	def aluno_dashboard():
		user = session.get('user')
		ra = user['ra']

		# Notas
		notas_q = (
			app.db.collection('grades')
			.where('aluno_ra', '==', ra)
			.order_by('created_at', direction=firestore.Query.DESCENDING)
		)
		notas_docs = notas_q.stream()
		notas = [doc.to_dict() for doc in notas_docs]

		# Faltas
		faltas_q = (
			app.db.collection('attendance')
			.where('aluno_ra', '==', ra)
			.order_by('date', direction=firestore.Query.DESCENDING)
		)
		faltas_docs = faltas_q.stream()
		faltas = [doc.to_dict() for doc in faltas_docs]

		return render_template('aluno/dashboard.html', user=user, notas=notas, faltas=faltas)

	# ---------------------- Rotas Professor ----------------------
	@app.get('/professor')
	@login_required(role='professor')
	def professor_dashboard():
		user = session.get('user')

		# Poderíamos listar alunos para facilitar o lançamento
		alunos_docs = app.db.collection('users').where('role', '==', 'aluno').stream()
		alunos = [doc.to_dict() for doc in alunos_docs]

		return render_template('professor/dashboard.html', user=user, alunos=alunos)

	@app.post('/professor/notas')
	@login_required(role='professor')
	def lancar_nota():
		user = session.get('user')
		aluno_ra = request.form.get('aluno_ra', '').strip()
		disciplina = request.form.get('disciplina', '').strip()
		try:
			nota = float(request.form.get('nota', ''))
		except ValueError:
			flash('Nota inválida.', 'error')
			return redirect(url_for('professor_dashboard'))

		if not aluno_ra or not disciplina or not (0.0 <= nota <= 10.0):
			flash('Preencha os campos corretamente (nota entre 0 e 10).', 'error')
			return redirect(url_for('professor_dashboard'))

		app.db.collection('grades').add({
			'aluno_ra': aluno_ra,
			'disciplina': disciplina,
			'nota': nota,
			'professor_ra': user['ra'],
			'created_at': firestore.SERVER_TIMESTAMP,
		})
		flash('Nota lançada com sucesso.', 'success')
		return redirect(url_for('professor_dashboard'))

	@app.post('/professor/faltas')
	@login_required(role='professor')
	def lancar_falta():
		user = session.get('user')
		aluno_ra = request.form.get('aluno_ra', '').strip()
		disciplina = request.form.get('disciplina', '').strip()
		try:
			faltas = int(request.form.get('faltas', ''))
		except ValueError:
			flash('Quantidade de faltas inválida.', 'error')
			return redirect(url_for('professor_dashboard'))

		if not aluno_ra or not disciplina or faltas < 0:
			flash('Preencha os campos corretamente.', 'error')
			return redirect(url_for('professor_dashboard'))

		app.db.collection('attendance').add({
			'aluno_ra': aluno_ra,
			'disciplina': disciplina,
			'faltas': faltas,
			'professor_ra': user['ra'],
			'date': firestore.SERVER_TIMESTAMP,
		})
		flash('Faltas registradas com sucesso.', 'success')
		return redirect(url_for('professor_dashboard'))

	# ---------------------- Rota de Seed (opcional para dev) ----------------------
	@app.get('/init-dev')
	def init_dev():
		if os.getenv('MODE') != 'dev':
			return ('Desabilitado', 403)

		# Cria um professor e um aluno de exemplo, se não existirem
		users_col = app.db.collection('users')
		aluno_ra = 'A123456'
		prof_ra = 'P654321'

		if not users_col.document(aluno_ra).get().exists:
			users_col.document(aluno_ra).set({
				'ra': aluno_ra,
				'name': 'Aluno Exemplo',
				'role': 'aluno',
				'password_hash': generate_password_hash('aluno123'),
			})
		if not users_col.document(prof_ra).get().exists:
			users_col.document(prof_ra).set({
				'ra': prof_ra,
				'name': 'Prof. Exemplo',
				'role': 'professor',
				'password_hash': generate_password_hash('prof123'),
			})

		return 'Usuários de exemplo criados (se não existiam).', 200

	return app


app = create_app()

if __name__ == '__main__':
	port = int(os.getenv('PORT', '8080'))
	app.run(host='0.0.0.0', port=port, debug=True)

