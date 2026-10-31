document.addEventListener("DOMContentLoaded", () => {
    const servico = document.getElementById("servico");
    const barbeiro = document.getElementById("barbeiro");
    const data = document.getElementById("data");
    const horario = document.getElementById("horario");
    const mensagem = document.getElementById("mensagemHorarios");

    if (!servico || !barbeiro || !data || !horario) return;

    function limparHorarios(texto) {
        horario.innerHTML = "";
        const option = document.createElement("option");
        option.value = "";
        option.textContent = texto;
        horario.appendChild(option);
        horario.disabled = true;
    }

    async function carregarHorarios() {
        if (!servico.value || !barbeiro.value || !data.value) {
            limparHorarios("Selecione serviço, barbeiro e data");
            mensagem.textContent = "Os horários disponíveis serão carregados após as seleções.";
            return;
        }

        limparHorarios("Carregando horários...");
        mensagem.textContent = "Consultando disponibilidade...";

        const params = new URLSearchParams({
            servico: servico.value,
            barbeiro: barbeiro.value,
            data: data.value
        });

        try {
            const response = await fetch(`/api/horarios?${params.toString()}`);
            const resultado = await response.json();

            if (!response.ok) {
                limparHorarios("Não foi possível carregar os horários");
                mensagem.textContent = "Confira a data e tente novamente.";
                return;
            }

            limparHorarios(resultado.horarios.length
                ? "Selecione um horário"
                : "Nenhum horário disponível");

            resultado.horarios.forEach((hora) => {
                const option = document.createElement("option");
                option.value = hora;
                option.textContent = hora;
                horario.appendChild(option);
            });

            horario.disabled = resultado.horarios.length === 0;
            mensagem.textContent = resultado.horarios.length
                ? "Horários exibidos conforme a disponibilidade atual."
                : "Não há horários disponíveis para essa seleção.";
        } catch (error) {
            limparHorarios("Erro ao consultar horários");
            mensagem.textContent = "Verifique sua conexão e tente novamente.";
        }
    }

    [servico, barbeiro, data].forEach((campo) => {
        campo.addEventListener("change", carregarHorarios);
    });

    const form = document.getElementById("formAgendamento");
    form?.addEventListener("submit", (event) => {
        if (horario.disabled || !horario.value) {
            event.preventDefault();
            mensagem.textContent = "Selecione um horário disponível antes de confirmar.";
        }
    });
});
