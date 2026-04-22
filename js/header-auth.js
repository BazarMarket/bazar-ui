window.BAZAR_API = (window.location.hostname === 'www.bazar.uk' || window.location.hostname === 'bazar.uk')
    ? 'https://admin.bazar.uk/api'
    : '/api';

(function () {
    /* Two-tone notification beep (Web Audio API, no file needed) */
    function playMsgSound() {
        try {
            var ctx = new (window.AudioContext || window.webkitAudioContext)();
            var osc  = ctx.createOscillator();
            var gain = ctx.createGain();
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.type = 'sine';
            osc.frequency.setValueAtTime(880, ctx.currentTime);
            osc.frequency.setValueAtTime(1100, ctx.currentTime + 0.12);
            gain.gain.setValueAtTime(0.25, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.35);
            osc.start(ctx.currentTime);
            osc.stop(ctx.currentTime + 0.35);
        } catch (e) {}
    }

    function updateHeader() {
        var name   = localStorage.getItem('bazar_username') || '';
        var phone  = localStorage.getItem('bazar_phone')    || '';
        var gender = localStorage.getItem('bazar_gender')   || 'male';

        var usernameEl = document.getElementById('header-username') ||
                         document.querySelector('.user-link__title');
        if (usernameEl) usernameEl.textContent = name;

        var phoneEl = document.getElementById('header-menu-phone') ||
                      document.querySelector('.user-menu-tel');
        if (phoneEl) phoneEl.textContent = phone;

        var avatarEl = document.getElementById('header-avatar') ||
                       document.querySelector('.user-link__photo');
        if (avatarEl) {
            var img = avatarEl.querySelector('img') || (avatarEl.tagName === 'IMG' ? avatarEl : null);
            if (img) {
                var savedAv = localStorage.getItem('bazar_avatar');
                img.src = savedAv || (gender === 'female' ? 'icon/woman.png' : 'icon/man.svg');
            }
        }

        updateFavCount();
        updateMsgCount();
        applyPlanBadge();

        /* Start live badge polling — updates unread count every 10s on any page */
        startMsgPolling();

        /* Fetch fresh data from API */
        var uid = localStorage.getItem('bazar_firebase_uid') || '';
        if (uid) {
            fetch(window.BAZAR_API + '/customers/' + encodeURIComponent(uid))
                .then(function(r) { return r.ok ? r.json() : {}; })
                .then(function(d) {
                    if (!d.exists) return;
                    if (d.name) {
                        localStorage.setItem('bazar_username', d.name);
                        var el = document.getElementById('header-username') || document.querySelector('.user-link__title');
                        if (el) el.textContent = d.name;
                    }
                    var isAdmin = d.is_admin ? '1' : '0';
                    localStorage.setItem('bazar_is_admin', isAdmin);
                    window.bazarIsAdmin = d.is_admin;
                    window.dispatchEvent(new CustomEvent('bazar:authReady', { detail: { is_admin: d.is_admin } }));
                    var plan = (d.plan || 'free').toLowerCase();
                    var daysLeft = parseInt(d.days_left || 0, 10);
                    var localPlan = (localStorage.getItem('bazar_plan') || 'free').toLowerCase();
                    var rank = { free: 0, pro: 1, vip: 2 };
                    /* Only update if API returns equal or higher plan (never downgrade) */
                    if ((rank[plan] || 0) >= (rank[localPlan] || 0)) {
                        localStorage.setItem('bazar_plan', plan);
                        if (daysLeft > 0) localStorage.setItem('bazar_days_left', daysLeft);
                        applyPlanBadge(plan, daysLeft);
                    } else {
                        /* Keep local plan, just refresh badge */
                        applyPlanBadge(localPlan, parseInt(localStorage.getItem('bazar_days_left') || '0', 10));
                    }
                })
                .catch(function() {});
        }
    }

    function applyPlanBadge(plan, daysLeft) {
        plan     = plan     || (localStorage.getItem('bazar_plan')      || 'free').toLowerCase();
        daysLeft = daysLeft !== undefined ? daysLeft : parseInt(localStorage.getItem('bazar_days_left') || '0', 10);

        /* Find badge element by id or fallback to class */
        var badge = document.getElementById('subPlanBadge') ||
                    document.querySelector('.subscription__stiker');
        var daysEl = document.getElementById('subDaysEl') ||
                     document.querySelector('.subscription__days');

        if (!badge) return;

        /* Style map */
        var styles = {
            free: { text: 'Free',  bg: '#22c55e', color: '#fff' },
            pro:  { text: 'PRO',   bg: '#ff9138', color: '#fff' },
            vip:  { text: 'VIP',   bg: '#c99a10', color: '#fff' }
        };
        var s = styles[plan] || styles.free;
        badge.textContent = s.text;
        badge.style.background = s.bg;
        badge.style.color = s.color;
        badge.style.borderRadius = '20px';
        badge.style.padding = '2px 10px';
        badge.style.fontWeight = '700';
        badge.style.fontSize = '12px';

        if (daysEl) {
            if (daysLeft > 0 && plan !== 'free') {
                daysEl.textContent = daysLeft + 'd';
                daysEl.style.display = '';
            } else {
                daysEl.textContent = '';
                daysEl.style.display = 'none';
            }
        }
    }

    function updateFavCount() {
        var count = 0;
        for (var i = 0; i < localStorage.length; i++) {
            var key = localStorage.key(i);
            if (key && key.indexOf('favorite_') === 0 && localStorage.getItem(key) === '1') count++;
        }
        var badge = document.getElementById('fav-count');
        if (badge) {
            badge.textContent = count;
            badge.style.display = count > 0 ? 'flex' : 'none';
        }
    }

    function setMsgBadge(count) {
        var badges = document.querySelectorAll('.icon-email .icon-item__namber');
        badges.forEach(function (b) {
            b.textContent = count;
            b.style.display = count > 0 ? 'flex' : 'none';
        });
        var byId = document.getElementById('msg-count');
        if (byId) {
            byId.textContent = count;
            byId.style.display = count > 0 ? 'flex' : 'none';
        }
        localStorage.setItem('bazar_unread_count', count);
    }

    function updateMsgCount() {
        var uid  = localStorage.getItem('bazar_firebase_uid') || '';
        var name = localStorage.getItem('bazar_username')     || '';
        if (!uid && !name) return;

        /* Show cached count immediately */
        var cached = parseInt(localStorage.getItem('bazar_unread_count') || '0', 10);
        if (cached > 0) setMsgBadge(cached);

        var url = '/api/chat/convs?uid=' + encodeURIComponent(uid);
        if (name) url += '&name=' + encodeURIComponent(name);

        fetch(url)
            .then(function (r) { return r.ok ? r.json() : { conversations: [] }; })
            .then(function (data) {
                var convs = data.conversations || [];
                var total = 0;
                convs.forEach(function (c) {
                    var isBuyer = c.buyer_id === uid;
                    total += isBuyer ? (c.unread_buyer || 0) : (c.unread_seller || 0);
                });
                setMsgBadge(total);
            })
            .catch(function () {});
    }

    /* Poll unread count every 10 seconds on every page */
    function startMsgPolling() {
        var uid  = localStorage.getItem('bazar_firebase_uid') || '';
        var name = localStorage.getItem('bazar_username')     || '';
        if (!uid && !name) return;

        /* Don't double-start if already running */
        if (window._bazarMsgPollTimer) return;

        /* On /messages page chat.js already handles sound — avoid double beep */
        var onMessagesPage = (window.location.pathname === '/messages' ||
                              window.location.pathname.indexOf('messages') !== -1);

        var _prevUnread = parseInt(localStorage.getItem('bazar_unread_count') || '0', 10);
        var _firstPoll  = true; /* skip sound on the very first poll */

        window._bazarMsgPollTimer = setInterval(function () {
            var url = '/api/chat/convs?uid=' + encodeURIComponent(uid);
            if (name) url += '&name=' + encodeURIComponent(name);
            fetch(url)
                .then(function (r) { return r.ok ? r.json() : { conversations: [] }; })
                .then(function (data) {
                    var convs = data.conversations || [];
                    var total = 0;
                    convs.forEach(function (c) {
                        var isBuyer = c.buyer_id === uid;
                        total += isBuyer ? (c.unread_buyer || 0) : (c.unread_seller || 0);
                    });
                    setMsgBadge(total);
                    /* Play sound when new messages arrive (not first poll, not on /messages) */
                    if (!_firstPoll && !onMessagesPage && total > _prevUnread) {
                        playMsgSound();
                    }
                    _prevUnread = total;
                    _firstPoll  = false;
                })
                .catch(function () { _firstPoll = false; });
        }, 10000);
    }

    window.updatePlanBadge = applyPlanBadge;

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', updateHeader);
    } else {
        updateHeader();
    }
})();
