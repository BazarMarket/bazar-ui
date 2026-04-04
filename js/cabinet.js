document.addEventListener('DOMContentLoaded', function () {

    /* ── Tab navigation ── */
    var navItems = document.querySelectorAll('.cab-nav__item[data-tab]');
    var panels = document.querySelectorAll('.cab-panel[data-panel]');

    function switchTab(tabId) {
        navItems.forEach(function (item) {
            item.classList.toggle('active', item.dataset.tab === tabId);
        });
        panels.forEach(function (panel) {
            panel.classList.toggle('active', panel.dataset.panel === tabId);
        });
        history.replaceState(null, '', '#' + tabId);
        if (window.innerWidth <= 768) {
            document.querySelector('.cab-content').scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
        if (tabId === 'messages' && typeof cabScrollToBottom === 'function') {
            setTimeout(cabScrollToBottom, 50);
        }
        if (tabId === 'favorites' && typeof renderFavorites === 'function') {
            renderFavorites();
        }
    }

    navItems.forEach(function (item) {
        item.addEventListener('click', function () {
            switchTab(this.dataset.tab);
        });
    });

    /* ── Deposit/Withdraw inner tabs ── */
    document.querySelectorAll('.cab-form-box__tab').forEach(function (tab) {
        tab.addEventListener('click', function () {
            var box = tab.closest('.cab-form-box');
            box.querySelectorAll('.cab-form-box__tab').forEach(function (t) { t.classList.remove('active'); });
            box.querySelectorAll('.cab-form-box__sub').forEach(function (s) { s.classList.remove('active'); });
            tab.classList.add('active');
            var target = box.querySelector('.cab-form-box__sub[data-sub="' + tab.dataset.tab + '"]');
            if (target) target.classList.add('active');
        });
    });

    /* ── Amount quick-select ── */
    document.querySelectorAll('.cab-amount-btn').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var group = btn.closest('.cab-amount-btns');
            group.querySelectorAll('.cab-amount-btn').forEach(function (b) { b.classList.remove('active'); });
            btn.classList.add('active');
            var input = btn.closest('.cab-form-box__sub').querySelector('input[type="number"]');
            if (input) input.value = btn.dataset.amount;
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

    /* ── Avatar upload ── */
    var avatarInput = document.getElementById('avatarInput');
    var avatarPreview = document.getElementById('avatarPreview');
    var sidebarAvatar = document.getElementById('sidebarAvatar');
    var headerAvatar = document.getElementById('headerAvatar');

    if (avatarInput) {
        document.getElementById('avatarUploadBox').addEventListener('click', function () {
            avatarInput.click();
        });
        avatarInput.addEventListener('change', function () {
            var file = this.files[0];
            if (!file) return;
            var reader = new FileReader();
            reader.onload = function (e) {
                if (avatarPreview) { avatarPreview.src = e.target.result; avatarPreview.classList.add('loaded'); avatarPreview.closest('.cab-avatar-upload').querySelector('.cab-avatar-upload__icon').style.display = 'none'; }
                if (sidebarAvatar) sidebarAvatar.src = e.target.result;
                if (headerAvatar) headerAvatar.src = e.target.result;
            };
            reader.readAsDataURL(file);
        });
    }

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

    /* ── Deposit form ── */
    var depositForm = document.getElementById('depositForm');
    if (depositForm) {
        depositForm.addEventListener('submit', function (e) {
            e.preventDefault();
            var amount = document.getElementById('depositAmount');
            if (!amount || !parseFloat(amount.value)) { showToast('Enter a valid amount', 'error'); return; }
            showToast('Top-up of £' + parseFloat(amount.value).toFixed(2) + ' initiated!');
        });
    }

    /* ── Withdraw form ── */
    var withdrawForm = document.getElementById('withdrawForm');
    if (withdrawForm) {
        withdrawForm.addEventListener('submit', function (e) {
            e.preventDefault();
            var amount = document.getElementById('withdrawAmount');
            if (!amount || !parseFloat(amount.value)) { showToast('Enter a valid amount', 'error'); return; }
            showToast('Withdrawal request sent!');
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
