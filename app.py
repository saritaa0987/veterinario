import os
import datetime
import jwt
from functools import wraps
from flask import Flask, request, jsonify, render_template
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('JWT_SECRET', 'chave_secreta_para_token')

def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        user=os.getenv('DB_USER', 'root'),
        password=os.getenv('DB_PASSWORD', ''),
        database=os.getenv('DB_NAME', 'veterinario_db')
    )

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]

        if not token:
            return jsonify({'mensagem': 'Acesso negado. Token não fornecido.'}), 401

        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user = data
        except jwt.ExpiredSignatureError:
            return jsonify({'mensagem': 'Token expirado. Faça login novamente.'}), 403
        except jwt.InvalidTokenError:
            return jsonify({'mensagem': 'Token inválido.'}), 403

        return f(current_user, *args, **kwargs)
    return decorated

@app.route('/')
def login_page():
    return render_template('login.html')

@app.route('/dashboard')
def dashboard_page():
    return render_template('dashboard.html')

# 1. ROTA DE LOGIN
@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    senha = data.get('senha')

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT * FROM usuarios WHERE email = %s AND senha = %s', (email, senha))
        usuario = cursor.fetchone()
        cursor.close()
        conn.close()

        if not usuario:
            return jsonify({'mensagem': 'E-mail ou senha inválidos!'}), 401

        payload = {
            'id': usuario['id'],
            'nome': usuario['nome'],
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)
        }
        token = jwt.encode(payload, app.config['SECRET_KEY'], algorithm="HS256")

        return jsonify({
            'token': token,
            'usuario': {'id': usuario['id'], 'nome': usuario['nome']}
        })
    except Exception as e:
        return jsonify({'mensagem': f'Erro de conexão com o Banco de Dados: {str(e)}'}), 500

# 2. BUSCAR TUTORES
@app.route('/api/tutores', methods=['GET'])
@token_required
def get_tutores(current_user):
    termo = request.args.get('termo', '')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    query = "SELECT id, nome, cpf_criptografado, telefone FROM tutores WHERE nome LIKE %s"
    cursor.execute(query, (f"%{termo}%",))
    tutores = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(tutores)

# 3. CADASTRAR PET ASSOCIADO AO TUTOR
@app.route('/api/pets', methods=['POST'])
@token_required
def add_pet(current_user):
    data = request.get_json()
    nome = data.get('nome')
    especie = data.get('especie')
    tutor_id = data.get('tutor_id')

    if not nome or not especie or not tutor_id:
        return jsonify({'mensagem': 'Preencha todos os campos!'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO pets (nome, especie, tutor_id) VALUES (%s, %s, %s)',
        (nome, especie, tutor_id)
    )
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({'mensagem': 'Pet cadastrado com sucesso!'}), 201

# 4. LISTAR AGENDAMENTOS ORDENADOS POR DATA
@app.route('/api/agendamentos', methods=['GET'])
@token_required
def get_agendamentos(current_user):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    query = """
        SELECT 
            a.id AS agendamento_id,
            a.data_hora,
            a.descricao,
            p.nome AS pet_nome,
            p.especie AS pet_especie,
            t.nome AS tutor_nome,
            t.telefone AS tutor_telefone
        FROM agendamentos a
        JOIN pets p ON a.pet_id = p.id
        JOIN tutores t ON p.tutor_id = t.id
        ORDER BY a.data_hora ASC;
    """
    cursor.execute(query)
    agendamentos = cursor.fetchall()
    cursor.close()
    conn.close()

    for item in agendamentos:
        if isinstance(item['data_hora'], datetime.datetime):
            item['data_hora'] = item['data_hora'].strftime('%d/%m/%Y %H:%M')

    return jsonify(agendamentos)

if __name__ == '__main__':
    app.run(debug=True, port=5000)