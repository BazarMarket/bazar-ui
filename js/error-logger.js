(function () {
    var API = 'https://admin.bazar.uk/api/log-error';
    var _sent = 0;
    var MAX_PER_SESSION = 10;

    function getPhone() {
        try { return localStorage.getItem('bazar_phone') || ''; } catch (e) { return ''; }
    }

    function send(type, message, page, phoneOverride) {
        if (_sent >= MAX_PER_SESSION) return;
        if (!message || message.length < 3) return;
        if (message.indexOf('extension') !== -1 || message.indexOf('chrome-extension') !== -1) return;
        // Browser-level noise: IndexedDB disconnect (Firebase auth storage, browser drops connection when tab is in background)
        if (message.indexOf('Connection to Indexed Database server lost') !== -1) return;
        // Browser-level noise: bare "Load failed" = Safari/iOS name for a failed fetch() due to no network / timeout
        // Only skip the exact bare message — real JS load errors include a URL or more context
        if (message.trim() === 'Load failed') return;
        _sent++;
        var phone = phoneOverride || getPhone();
        var payload = JSON.stringify({ type: type, message: String(message).slice(0, 2000), page: page || location.pathname, phone: phone });
        try {
            navigator.sendBeacon
                ? navigator.sendBeacon(API, new Blob([payload], { type: 'application/json' }))
                : fetch(API, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: payload,
                    keepalive: true
                }).catch(function () {});
        } catch (e) {}
    }

    window.bzLogError = send;

    window.addEventListener('error', function (e) {
        if (!e.message) return;
        send('frontend', (e.message || '') + (e.filename ? ' @ ' + e.filename + ':' + e.lineno : ''));
    });

    window.addEventListener('unhandledrejection', function (e) {
        var msg = '';
        if (e.reason) {
            msg = e.reason.message || String(e.reason);
        }
        if (!msg || msg === 'undefined') return;
        var type = 'frontend';
        if (msg.indexOf('Firebase') !== -1 || msg.indexOf('auth/') !== -1) type = 'firebase';
        if (msg.indexOf('Stripe') !== -1 || msg.indexOf('stripe') !== -1) type = 'stripe';
        send(type, msg);
    });
})();
