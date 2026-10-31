document.addEventListener("DOMContentLoaded", () => {
    const form = document.querySelector('form[action$="/cadastro"]');
    if (!form) return;

    form.addEventListener("submit", (event) => {
        const senha = document.getElementById("senha");
        const confirmar = document.getElementById("confirmar_senha");

        if (senha && confirmar && senha.value !== confirmar.value) {
            event.preventDefault();
            confirmar.setCustomValidity("As senhas não coincidem.");
            confirmar.reportValidity();
        }
    });

    const confirmar = document.getElementById("confirmar_senha");
    confirmar?.addEventListener("input", () => confirmar.setCustomValidity(""));
});
