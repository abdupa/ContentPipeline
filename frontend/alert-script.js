// alert-script.js (V2.0.1 - FINAL FIX)
(function () {
    document.addEventListener('DOMContentLoaded', function () {
        const alertForm = document.getElementById('po-alert-form');
        if (!alertForm) { return; }
        
        if (typeof poAlertData === 'undefined') {
            console.error('Price Alert Data object (poAlertData) is missing.');
            return;
        }
        const ajaxUrl = poAlertData.ajax_url;
        const nonce = poAlertData.nonce;

        const loadingSpinner = alertForm.querySelector('.po-alert-loading');
        const successMessage = alertForm.querySelector('.po-alert-success');
        const errorMessage = alertForm.querySelector('.po-alert-error');
        const formInputs = alertForm.querySelectorAll('input, button');

        alertForm.addEventListener('submit', function (event) {
            event.preventDefault();

            // --- V2.0.1 FIX: Read the form data BEFORE disabling the inputs ---
            const formData = new FormData(alertForm);
            formData.append('action', 'po_subscribe_to_alert');
            formData.append('nonce', nonce);

            // Now, update the UI
            loadingSpinner.style.display = 'block';
            successMessage.style.display = 'none';
            errorMessage.style.display = 'none';
            formInputs.forEach(el => el.disabled = true);

            fetch(ajaxUrl, {
                method: 'POST',
                body: new URLSearchParams(formData),
            })
            .then(response => {
                if (!response.ok) { throw new Error(`Server responded with an error: ${response.statusText}`); }
                return response.json();
            })
            .then(result => {
                if (result.success) {
                    loadingSpinner.style.display = 'none';
                    successMessage.textContent = result.data.message;
                    successMessage.style.display = 'block';
                } else {
                    throw new Error(result.data.message || 'An unknown error occurred.');
                }
            })
            .catch((error) => {
                loadingSpinner.style.display = 'none';
                errorMessage.textContent = 'Error: ' + error.message;
                errorMessage.style.display = 'block';
                formInputs.forEach(el => el.disabled = false);
            });
        });
    });
})();