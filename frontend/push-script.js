// push-script.js
(function () {
    // Use OneSignal's command queue to ensure the SDK is ready before we run any code.
    window.OneSignal = window.OneSignal || [];
    OneSignal.push(function() {
        const pushButton = document.getElementById('po-push-alert-button');
        if (!pushButton) { return; }

        pushButton.addEventListener('click', function () {
            pushButton.disabled = true;
            pushButton.querySelector('span').textContent = 'Subscribing...';

            OneSignal.isPushNotificationsEnabled(function(isEnabled) {
                if (isEnabled) {
                    // User is already subscribed to the site, get their ID
                    OneSignal.getUserId(function(playerId) {
                        saveSubscription(playerId);
                    });
                } else {
                    // User is not subscribed, show the main prompt
                    OneSignal.showSlidedownPrompt().then(() => {
                        OneSignal.getUserId(function(newPlayerId) {
                            if (newPlayerId) {
                                saveSubscription(newPlayerId);
                            } else {
                                // User closed prompt without subscribing.
                                pushButton.disabled = false;
                                pushButton.querySelector('span').textContent = 'Notify me via Push Alert';
                            }
                        });
                    });
                }
            });
        });

        function saveSubscription(playerId) {
            if (!playerId) { return; }
            
            // The 'poPushData' object is passed from our PHP file.
            const ajaxUrl = poPushData.ajax_url;
            const nonce = poPushData.nonce;
            const productId = poPushData.product_id;

            const formData = new FormData();
            formData.append('action', 'po_subscribe_to_push_alert');
            formData.append('nonce', nonce);
            formData.append('product_id', productId);
            formData.append('player_id', playerId);

            fetch(ajaxUrl, {
                method: 'POST',
                body: new URLSearchParams(formData),
            })
            .then(response => response.json())
            .then(result => {
                if (result.success) {
                    pushButton.querySelector('span').textContent = '✅ Subscribed!';
                } else {
                    pushButton.querySelector('span').textContent = result.data.message || 'Already Subscribed';
                }
            })
            .catch(error => {
                console.error('Push subscription save error:', error);
                pushButton.querySelector('span').textContent = 'Error - Try Again';
                pushButton.disabled = false;
            });
        }
    });
})();