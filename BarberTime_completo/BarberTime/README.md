# BarberTime

Sistema demonstrativo de agendamento para barbearia, feito com Python, Flask, SQLite, HTML, CSS e JavaScript.

## Requisitos
- Python 3.10 ou superior recomendado.

## Instalação no Windows

Abra o terminal na pasta do projeto e execute:

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python app.py
```

Abra `http://127.0.0.1:5000` no navegador.

## Funcionalidades
- Cadastro de clientes com hash de senha.
- Login e logout com sessão.
- Serviços e barbeiros de exemplo criados automaticamente.
- Consulta de horários por serviço, profissional e data.
- Reserva de horários e prevenção básica de conflitos.
- Página de agendamentos do cliente e cancelamento de reservas.

## Observações importantes
- Os serviços, barbeiros e horários são dados de exemplo. Edite-os conforme sua barbearia.
- Horário de funcionamento de exemplo: 09:00–18:00, com pausa entre 12:00 e 13:00.
- O sistema não possui painel administrativo nesta versão.
- Antes de publicar: configure uma `BARBERTIME_SECRET_KEY` forte por variável de ambiente, desligue o modo debug, use HTTPS, adicione proteção CSRF, controle de tentativas de login, política de cancelamento e testes de concorrência para reservas.
- A lógica de horários é uma base didática e precisa ser revisada para regras reais de funcionamento, feriados, fusos horários, serviços consecutivos e múltiplos profissionais.
- O arquivo `banco.db` é criado automaticamente na primeira execução.
