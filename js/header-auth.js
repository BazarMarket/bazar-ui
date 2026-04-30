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
                    if (d.avatar) {
                        try { localStorage.setItem('bazar_avatar', d.avatar); } catch(ex) {}
                        var avEl = document.getElementById('header-avatar') || document.querySelector('.user-link__photo');
                        if (avEl) {
                            var avImg = avEl.querySelector('img') || (avEl.tagName === 'IMG' ? avEl : null);
                            if (avImg) avImg.src = d.avatar;
                        }
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
        var mobBadge = document.getElementById('mob-fav-badge');
        if (mobBadge) {
            mobBadge.textContent = count;
            mobBadge.style.display = count > 0 ? 'inline-block' : 'none';
        }
        return count;
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
        var mobBadge = document.getElementById('mob-msg-badge');
        if (mobBadge) {
            mobBadge.textContent = count;
            mobBadge.style.display = count > 0 ? 'inline-block' : 'none';
        }
        localStorage.setItem('bazar_unread_count', count);
    }
    window.bazarSetMsgBadge = setMsgBadge;

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
    window.updateFavCount  = updateFavCount;

    function initHearts() {
        var uid = localStorage.getItem('bazar_firebase_uid');
        if (!uid) return;
        document.querySelectorAll('.card__heart').forEach(function(btn) {
            var card = btn.closest('.card');
            var link = card ? card.querySelector('a.card-link') : null;
            var href = link ? (link.getAttribute('href') || '') : '';
            var match = href.match(/[?&]id=(\d+)/);
            var id = match ? match[1] : href.replace(/[^0-9]/g, '');
            if (!id) return;
            btn.dataset.listingId = id;
            if (localStorage.getItem('favorite_' + id) === '1') {
                btn.classList.add('active');
            }
        });
    }

    function _getHeartId(btn) {
        if (btn.dataset.listingId) return btn.dataset.listingId;
        var container = btn.closest('.card') || btn.closest('.product');
        if (!container) return '';
        var link = container.querySelector('[href*="id="]');
        if (!link) return '';
        var m = (link.getAttribute('href') || '').match(/[?&]id=(\d+)/);
        var id = m ? m[1] : '';
        if (id) btn.dataset.listingId = id;
        return id;
    }

    document.addEventListener('click', function(e) {
        var btn = e.target.closest('.card__heart');
        if (!btn) return;
        e.preventDefault();
        e.stopImmediatePropagation();

        var uid = localStorage.getItem('bazar_firebase_uid');
        if (!uid) return;

        var id = _getHeartId(btn);
        if (!id) return;

        var key = 'favorite_' + id;
        var nowFav = localStorage.getItem(key) !== '1';
        if (nowFav) {
            localStorage.setItem(key, '1');
        } else {
            localStorage.removeItem(key);
        }
        btn.classList.toggle('active', nowFav);
        btn.classList.toggle('icon-heart', !nowFav);
        btn.classList.toggle('icon-heart-full', nowFav);

        /* Sync list ↔ grid: update all other hearts with same card ID */
        document.querySelectorAll('.card__heart').forEach(function(h) {
            if (h === btn) return;
            if (_getHeartId(h) === id) {
                h.classList.toggle('active', nowFav);
                h.classList.toggle('icon-heart', !nowFav);
                h.classList.toggle('icon-heart-full', nowFav);
            }
        });

        updateFavCount();
    }, true);

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            updateHeader();
            initHearts();
        });
    } else {
        updateHeader();
        initHearts();
    }
})();

/* ── English-only input validation (global, all pages) ──────────────────── */
(function () {
    var _toast = null;
    var _toastTimer = null;

    function showEngToast() {
        if (!_toast) {
            _toast = document.createElement('div');
            _toast.textContent = 'Only English characters are allowed';
            _toast.style.cssText = [
                'position:fixed', 'top:70px', 'right:16px', 'z-index:99999',
                'background:#e31836', 'color:#fff', 'font-size:13px', 'font-weight:600',
                'padding:9px 16px', 'border-radius:8px',
                'box-shadow:0 3px 12px rgba(0,0,0,0.22)',
                'pointer-events:none', 'transition:opacity .25s',
                'opacity:0'
            ].join(';');
            document.body.appendChild(_toast);
        }
        _toast.style.opacity = '1';
        clearTimeout(_toastTimer);
        _toastTimer = setTimeout(function () {
            if (_toast) _toast.style.opacity = '0';
        }, 2200);
    }

    /* Returns true if el should be validated for English-only input */
    function shouldValidate(el) {
        if (!el) return false;
        var tag = el.tagName;
        if (tag !== 'INPUT' && tag !== 'TEXTAREA') return false;
        var type = (el.type || 'text').toLowerCase();
        var skip = ['hidden', 'checkbox', 'radio', 'file', 'submit',
                    'button', 'reset', 'image', 'range', 'color',
                    'date', 'time', 'datetime-local', 'month', 'week',
                    'number', 'tel'];
        if (skip.indexOf(type) !== -1) return false;
        if (el.inputMode === 'numeric' || el.inputMode === 'decimal') return false;
        if (el.classList.contains('otp-input')) return false;
        if (el.classList.contains('modal-number-input')) return false;
        return true;
    }

    /* Strip non-ASCII characters from string */
    function toEnglish(str) {
        return str.replace(/[^\x00-\x7F]/g, '');
    }

    /* Filter on every input event (keyboard, IME, voice, autofill) */
    document.addEventListener('input', function (e) {
        var el = e.target;
        if (!shouldValidate(el)) return;
        var val = el.value;
        if (/[^\x00-\x7F]/.test(val)) {
            var pos = el.selectionStart || 0;
            var filtered = toEnglish(val);
            el.value = filtered;
            var newPos = Math.min(pos, filtered.length);
            try { el.setSelectionRange(newPos, newPos); } catch (_) {}
            showEngToast();
        }
    }, true);

    /* Also intercept paste separately to handle it before `input` fires */
    document.addEventListener('paste', function (e) {
        var el = e.target;
        if (!shouldValidate(el)) return;
        var pasted = (e.clipboardData || window.clipboardData || {}).getData('text') || '';
        if (/[^\x00-\x7F]/.test(pasted)) {
            e.preventDefault();
            var filtered = toEnglish(pasted);
            var start = el.selectionStart || 0;
            var end   = el.selectionEnd   || 0;
            var cur   = el.value;
            el.value  = cur.substring(0, start) + filtered + cur.substring(end);
            var np    = start + filtered.length;
            try { el.setSelectionRange(np, np); } catch (_) {}
            el.dispatchEvent(new Event('input', { bubbles: true }));
            showEngToast();
        }
    }, true);
})();

/* ── Mobile bottom-nav handlers (global, available on all pages) ── */
if (typeof window._bzIsLoggedIn !== 'function') {
    window._bzIsLoggedIn = function() {
        return !!(localStorage.getItem('bazar_firebase_uid') && localStorage.getItem('bazar_username'));
    };
}
if (typeof window.handleMobileProfile !== 'function') {
    window.handleMobileProfile = function(e) {
        e.preventDefault();
        if (_bzIsLoggedIn()) { window.location.href = '/cabinet'; }
        else if (typeof openCreateAccountModal === 'function') openCreateAccountModal();
    };
}
if (typeof window.handleMobileFavorites !== 'function') {
    window.handleMobileFavorites = function(e) {
        e.preventDefault();
        if (_bzIsLoggedIn()) { window.location.href = '/cabinet/favorites'; }
        else if (typeof openCreateAccountModal === 'function') openCreateAccountModal();
    };
}
if (typeof window.handleMobileMessages !== 'function') {
    window.handleMobileMessages = function(e) {
        e.preventDefault();
        if (_bzIsLoggedIn()) { window.location.href = '/messages'; }
        else if (typeof openCreateAccountModal === 'function') openCreateAccountModal();
    };
}

/* ── Card image hover segments (desktop only) ── */
(function() {
    if (window.innerWidth < 768) return;

    function getImgDiv(target) {
        return target.closest ? target.closest('.card__img[data-imgs]') : null;
    }
    function buildSegs(imgDiv, imgs) {
        var segs = imgDiv.querySelector('.card-img-segs');
        if (segs) return segs;
        segs = document.createElement('div');
        segs.className = 'card-img-segs';
        var w = Math.min(imgs.length, 8);
        segs.style.width = (w * 22 + (w - 1) * 4) + 'px';
        for (var i = 0; i < imgs.length; i++) {
            var s = document.createElement('span');
            s.className = 'card-img-seg' + (i === 0 ? ' active' : '');
            segs.appendChild(s);
        }
        imgDiv.appendChild(segs);
        return segs;
    }
    function setActive(segs, idx) {
        var els = segs.querySelectorAll('.card-img-seg');
        els.forEach(function(s, i) { s.classList.toggle('active', i === idx); });
    }

    document.addEventListener('mouseenter', function(e) {
        var imgDiv = getImgDiv(e.target);
        if (!imgDiv) return;
        var imgs = imgDiv.getAttribute('data-imgs').split(',').filter(Boolean);
        if (imgs.length < 2) return;
        var segs = buildSegs(imgDiv, imgs);
        segs.classList.add('visible');
        var img = imgDiv.querySelector('img.img-cover');
        if (img && !imgDiv._origSrc) imgDiv._origSrc = img.src;
    }, true);

    document.addEventListener('mousemove', function(e) {
        var imgDiv = getImgDiv(e.target);
        if (!imgDiv) return;
        var segs = imgDiv.querySelector('.card-img-segs');
        if (!segs || !segs.classList.contains('visible')) return;
        var imgs = imgDiv.getAttribute('data-imgs').split(',').filter(Boolean);
        if (imgs.length < 2) return;
        var rect = imgDiv.getBoundingClientRect();
        var pct  = (e.clientX - rect.left) / rect.width;
        var idx  = Math.max(0, Math.min(imgs.length - 1, Math.floor(pct * imgs.length)));
        var img  = imgDiv.querySelector('img.img-cover');
        if (img && img.src !== imgs[idx]) img.src = imgs[idx];
        setActive(segs, idx);
    });

    document.addEventListener('mouseleave', function(e) {
        var imgDiv = getImgDiv(e.target);
        if (!imgDiv) return;
        if (imgDiv.contains(e.relatedTarget)) return;
        var segs = imgDiv.querySelector('.card-img-segs');
        if (segs) { segs.classList.remove('visible'); setActive(segs, 0); }
        var img = imgDiv.querySelector('img.img-cover');
        if (img && imgDiv._origSrc) { img.src = imgDiv._origSrc; imgDiv._origSrc = null; }
    }, true);
})();
