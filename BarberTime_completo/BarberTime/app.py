import os
import re
import sqlite3
from datetime import date, datetime, timedelta
from functools import wraps
from pathlib import Path

from flask import (
    Flask, flash, g, redirect, render_template, request,
    session, url_for
)
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "banco.db"

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get(
    "BARBERTIME_SECRET_KEY",
    "dev-only-change-this-secret-before-deployment"
)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"


def connect_db():
    conn = sqlite3.connect(DATABASE, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 10000")
    return conn


def init_db():
    with connect_db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT NOT NULL COLLATE NOCASE UNIQUE,
            telefone TEXT NOT NULL,
            senha_hash TEXT NOT NULL,
            criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS servicos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL UNIQUE,
            descricao TEXT NOT NULL DEFAULT '',
            duracao_min INTEGER NOT NULL CHECK (duracao_min > 0),
            preco_centavos INTEGER NOT NULL CHECK (preco_centavos >= 0),
            ativo INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS barbeiros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            ativo INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS agendamentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER NOT NULL REFERENCES clientes(id),
            servico_id INTEGER NOT NULL REFERENCES servicos(id),
            barbeiro_id INTEGER NOT NULL REFERENCES barbeiros(id),
            data TEXT NOT NULL,
            horario TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'confirmado'
                CHECK (status IN ('confirmado', 'cancelado')),
            criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_agendamento_data_barbeiro
            ON agendamentos(data, barbeiro_id, status);
        """)

        if conn.execute("SELECT COUNT(*) FROM servicos").fetchone()[0] == 0:
            conn.executemany("""
                INSERT INTO servicos (nome, descricao, duracao_min, preco_centavos)
                VALUES (?, ?, ?, ?)
            """, [
                ("Corte de cabelo", "Corte tradicional ou social.", 30, 3500),
                ("Corte degradê", "Corte degradê com acabamento.", 45, 4500),
                ("Barba", "Aparar e alinhar a barba.", 20, 2500),
                ("Cabelo + barba", "Pacote de cabelo e barba.", 60, 5500),
                ("Sobrancelha", "Acabamento de sobrancelha.", 15, 1500),
            ])

        if conn.execute("SELECT COUNT(*) FROM barbeiros").fetchone()[0] == 0:
            conn.executemany(
                "INSERT INTO barbeiros (nome) VALUES (?)",
                [("Rafael",), ("Lucas",), ("Matheus",)]
            )


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "cliente_id" not in session:
            flash("Entre na sua conta para continuar.", "erro")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def parse_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def time_to_minutes(value):
    try:
        parsed = datetime.strptime(value, "%H:%M")
        return parsed.hour * 60 + parsed.minute
    except (TypeError, ValueError):
        return None


def slots_for_day(conn, barber_id, service_id, day):
    service = conn.execute(
        "SELECT duracao_min FROM servicos WHERE id = ? AND ativo = 1",
        (service_id,)
    ).fetchone()
    if not service:
        return []

    duration = service["duracao_min"]
    # Horário de funcionamento de exemplo: 09h às 18h, pausa 12h–13h.
    slots = []
    current = 9 * 60
    closing = 18 * 60
    now = datetime.now()
    existing = conn.execute("""
        SELECT a.horario, s.duracao_min
        FROM agendamentos a
        JOIN servicos s ON s.id = a.servico_id
        WHERE a.barbeiro_id = ? AND a.data = ? AND a.status = 'confirmado'
    """, (barber_id, day.isoformat())).fetchall()

    occupied = []
    for row in existing:
        start = time_to_minutes(row["horario"])
        if start is not None:
            occupied.append((start, start + row["duracao_min"]))

    while current + duration <= closing:
        # Pular o intervalo de almoço e qualquer serviço que atravesse o intervalo.
        if current < 13 * 60 and current + duration > 12 * 60:
            current += 15
            continue
        if current < 12 * 60 and current + duration > 12 * 60:
            current += 15
            continue

        start_text = f"{current // 60:02d}:{current % 60:02d}"
        candidate_end = current + duration
        conflict = any(current < end and candidate_end > start for start, end in occupied)
        if day == now.date() and current <= now.hour * 60 + now.minute:
            conflict = True
        if not conflict:
            slots.append(start_text)
        current += 15
    return slots


@app.context_processor
def shared_template_values():
    return {"logged_in": "cliente_id" in session,
            "cliente_nome": session.get("cliente_nome")}


@app.route("/")
def inicio():
    with connect_db() as conn:
        servicos = conn.execute(
            "SELECT * FROM servicos WHERE ativo = 1 ORDER BY id"
        ).fetchall()
    return render_template("index.html", servicos=servicos)


@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if request.method == "GET":
        return render_template("cadastro.html")

    nome = request.form.get("nome", "").strip()
    email = request.form.get("email", "").strip().lower()
    telefone = request.form.get("telefone", "").strip()
    senha = request.form.get("senha", "")
    confirmar = request.form.get("confirmar_senha", "")

    if not nome or not email or not telefone or not senha:
        flash("Preencha todos os campos.", "erro")
        return redirect(url_for("cadastro"))
    if len(nome) > 100:
        flash("O nome deve ter no máximo 100 caracteres.", "erro")
        return redirect(url_for("cadastro"))
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) or len(email) > 254:
        flash("Informe um e-mail válido.", "erro")
        return redirect(url_for("cadastro"))
    if len(telefone) > 20 or len(telefone) < 8:
        flash("Informe um telefone válido.", "erro")
        return redirect(url_for("cadastro"))
    if len(senha) < 8 or len(senha) > 128:
        flash("A senha deve ter entre 8 e 128 caracteres.", "erro")
        return redirect(url_for("cadastro"))
    if senha != confirmar:
        flash("As senhas não coincidem.", "erro")
        return redirect(url_for("cadastro"))

    try:
        with connect_db() as conn:
            conn.execute("""
                INSERT INTO clientes (nome, email, telefone, senha_hash)
                VALUES (?, ?, ?, ?)
            """, (nome, email, telefone, generate_password_hash(senha)))
        flash("Conta criada! Agora você pode entrar.", "sucesso")
        return redirect(url_for("login"))
    except sqlite3.IntegrityError:
        flash("Não foi possível criar a conta. Esse e-mail pode já estar cadastrado.", "erro")
        return redirect(url_for("cadastro"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    senha = request.form.get("senha", "")

    with connect_db() as conn:
        cliente = conn.execute(
            "SELECT * FROM clientes WHERE email = ?", (email,)
        ).fetchone()

    if not cliente or not check_password_hash(cliente["senha_hash"], senha):
        flash("E-mail ou senha incorretos.", "erro")
        return redirect(url_for("login"))

    session.clear()
    session["cliente_id"] = cliente["id"]
    session["cliente_nome"] = cliente["nome"]
    flash("Login realizado com sucesso!", "sucesso")
    return redirect(url_for("agendamento"))


@app.route("/sair", methods=["POST"])
def sair():
    session.clear()
    flash("Você saiu da sua conta.", "sucesso")
    return redirect(url_for("inicio"))


@app.route("/agendamento", methods=["GET", "POST"])
@login_required
def agendamento():
    with connect_db() as conn:
        servicos = conn.execute(
            "SELECT * FROM servicos WHERE ativo = 1 ORDER BY nome"
        ).fetchall()
        barbeiros = conn.execute(
            "SELECT * FROM barbeiros WHERE ativo = 1 ORDER BY nome"
        ).fetchall()

        if request.method == "POST":
            servico_id = request.form.get("servico", type=int)
            barbeiro_id = request.form.get("barbeiro", type=int)
            data_texto = request.form.get("data", "")
            horario = request.form.get("horario", "")
            dia = parse_date(data_texto)

            if not servico_id or not barbeiro_id or not dia or time_to_minutes(horario) is None:
                flash("Confira o serviço, profissional, data e horário.", "erro")
                return redirect(url_for("agendamento"))

            if dia < date.today():
                flash("Não é possível agendar em uma data passada.", "erro")
                return redirect(url_for("agendamento"))

            servico = conn.execute(
                "SELECT id FROM servicos WHERE id = ? AND ativo = 1",
                (servico_id,)
            ).fetchone()
            barbeiro = conn.execute(
                "SELECT id FROM barbeiros WHERE id = ? AND ativo = 1",
                (barbeiro_id,)
            ).fetchone()
            if not servico or not barbeiro:
                flash("Serviço ou profissional inválido.", "erro")
                return redirect(url_for("agendamento"))

            disponiveis = slots_for_day(conn, barbeiro_id, servico_id, dia)
            if horario not in disponiveis:
                flash("Esse horário não está mais disponível. Escolha outro.", "erro")
                return redirect(url_for("agendamento"))

            conn.execute("""
                INSERT INTO agendamentos
                    (cliente_id, servico_id, barbeiro_id, data, horario)
                VALUES (?, ?, ?, ?, ?)
            """, (session["cliente_id"], servico_id, barbeiro_id, dia.isoformat(), horario))
            flash("Agendamento confirmado!", "sucesso")
            return redirect(url_for("meus_agendamentos"))

    return render_template(
        "agendamento.html", servicos=servicos, barbeiros=barbeiros,
        hoje=date.today().isoformat()
    )


@app.route("/api/horarios")
@login_required
def api_horarios():
    servico_id = request.args.get("servico", type=int)
    barbeiro_id = request.args.get("barbeiro", type=int)
    dia = parse_date(request.args.get("data", ""))

    if not servico_id or not barbeiro_id or not dia or dia < date.today():
        return {"horarios": []}, 400

    with connect_db() as conn:
        horarios = slots_for_day(conn, barbeiro_id, servico_id, dia)
    return {"horarios": horarios}


@app.route("/meus-agendamentos")
@login_required
def meus_agendamentos():
    with connect_db() as conn:
        agendamentos = conn.execute("""
            SELECT a.id, a.data, a.horario, a.status,
                   s.nome AS servico, s.duracao_min, s.preco_centavos,
                   b.nome AS barbeiro
            FROM agendamentos a
            JOIN servicos s ON s.id = a.servico_id
            JOIN barbeiros b ON b.id = a.barbeiro_id
            WHERE a.cliente_id = ?
            ORDER BY a.data DESC, a.horario DESC
        """, (session["cliente_id"],)).fetchall()
    return render_template("meus-agendamentos.html", agendamentos=agendamentos)


@app.route("/cancelar/<int:agendamento_id>", methods=["POST"])
@login_required
def cancelar_agendamento(agendamento_id):
    with connect_db() as conn:
        resultado = conn.execute("""
            UPDATE agendamentos
            SET status = 'cancelado'
            WHERE id = ? AND cliente_id = ? AND status = 'confirmado'
        """, (agendamento_id, session["cliente_id"]))
    if resultado.rowcount:
        flash("Agendamento cancelado.", "sucesso")
    else:
        flash("Não foi possível cancelar esse agendamento.", "erro")
    return redirect(url_for("meus_agendamentos"))


@app.errorhandler(404)
def pagina_nao_encontrada(_error):
    return render_template("404.html"), 404


if __name__ == "__main__":
    init_db()
    # Apenas para desenvolvimento local. Não usar debug=True em produção.
    app.run(debug=True)
