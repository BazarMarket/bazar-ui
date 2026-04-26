document.addEventListener('DOMContentLoaded', function () {

    /* ── Tab navigation ── */
    var navItems = document.querySelectorAll('.cab-nav__item[data-tab]');
    var panels = document.querySelectorAll('.cab-panel[data-panel]');

    function switchTab(tabId, sourceEl) {
        navItems.forEach(function (item) { item.classList.remove('active'); });
        if (sourceEl) {
            sourceEl.classList.add('active');
        } else {
            var first = document.querySelector('.cab-nav__item[data-tab="' + tabId + '"]');
            if (first) first.classList.add('active');
        }
        var panelId = tabId;
        panels.forEach(function (panel) {
            panel.classList.toggle('active', panel.dataset.panel === panelId);
        });
        history.replaceState(null, '', tabId === 'dashboard' ? '/cabinet' : '/cabinet/' + tabId);
        if (window.innerWidth <= 768) {
            document.querySelector('.cab-content').scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
        if (tabId === 'messages' && typeof cabScrollToBottom === 'function') {
            setTimeout(cabScrollToBottom, 50);
        }
        if (tabId === 'favorites' && typeof renderFavorites === 'function') {
            renderFavorites();
        }
        if (tabId === 'payments' && typeof loadPayments === 'function') {
            loadPayments();
        }
        if (tabId === 'my-ads' && typeof loadMyAds === 'function') {
            loadMyAds();
        }
        if ((tabId === 'profile' || tabId === 'settings') && typeof populateProfileStats === 'function') {
            populateProfileStats();
        }
        if (tabId === 'tickets' && typeof loadTickets === 'function') {
            loadTickets();
        }
    }

    window._cabSwitchTab = switchTab;

    navItems.forEach(function (item) {
        item.addEventListener('click', function () {
            switchTab(this.dataset.tab, this);
        });
    });


    /* ── Ads filter tabs ── */
    document.querySelectorAll('.cab-filter-btn').forEach(function (btn) {
        btn.addEventListener('click', function () {
            btn.closest('.cab-ads-filter').querySelectorAll('.cab-filter-btn').forEach(function (b) { b.classList.remove('active'); });
            btn.classList.add('active');
        });
    });

    /* ── FAQ accordion ── */
    document.querySelectorAll('.cab-faq-item').forEach(function (item) {
        var head = item.querySelector('.cab-faq-head');
        if (!head) return;
        head.addEventListener('click', function () {
            var isOpen = item.classList.contains('open');
            document.querySelectorAll('.cab-faq-item').forEach(function (i) { i.classList.remove('open'); });
            if (!isOpen) item.classList.add('open');
        });
    });

    /* ── Profile form ── */
    var profileForm = document.getElementById('profileForm');
    if (profileForm) {
        profileForm.addEventListener('submit', function (e) {
            e.preventDefault();
            var fn = document.getElementById('fieldFirstName');
            var ln = document.getElementById('fieldLastName');
            var nameEl = document.getElementById('sidebarName');
            var headerName = document.getElementById('headerName');
            if (fn && ln && nameEl) { nameEl.textContent = fn.value + ' ' + ln.value; }
            if (fn && ln && headerName) { headerName.textContent = fn.value + ' ' + ln.value; }
            showToast('Profile saved!');
        });
    }


    /* ── Delete ad row ── */
    document.querySelectorAll('.cab-delete-ad').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var row = btn.closest('tr');
            if (row && confirm('Delete this ad?')) {
                row.style.opacity = '0';
                row.style.transition = '0.3s';
                setTimeout(function () { row.remove(); }, 310);
            }
        });
    });

    /* ── Remove favorite ── */
    document.querySelectorAll('.cab-remove-fav').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var card = btn.closest('.cab-fav-card');
            if (card) { card.style.opacity = '0'; card.style.transition = '0.3s'; setTimeout(function () { card.remove(); }, 310); }
        });
    });

    /* ── Mark all notifications read ── */
    var markRead = document.getElementById('markAllRead');
    if (markRead) {
        markRead.addEventListener('click', function () {
            document.querySelectorAll('.cab-table tr.unread').forEach(function (r) { r.classList.remove('unread'); });
            var badge = document.querySelector('.cab-nav__item[data-tab="notifications"] .cab-nav__badge');
            if (badge) badge.remove();
        });
    }

    /* ── Toast ── */
    function showToast(msg, type) {
        var t = document.createElement('div');
        t.textContent = msg;
        t.style.cssText = 'position:fixed;bottom:32px;left:50%;transform:translateX(-50%);background:' + (type === 'error' ? '#e52d2e' : '#1a8c3e') + ';color:#fff;font-family:Poppins,sans-serif;font-size:14px;font-weight:500;padding:12px 24px;border-radius:8px;box-shadow:0 4px 20px rgba(0,0,0,.15);z-index:9999;transition:opacity .4s;pointer-events:none';
        document.body.appendChild(t);
        setTimeout(function () { t.style.opacity = '0'; setTimeout(function () { t.remove(); }, 400); }, 2800);
    }

});
