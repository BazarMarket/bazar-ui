(function () {
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
        /* also the dedicated id="msg-count" if present */
        var byId = document.getElementById('msg-count');
        if (byId) {
            byId.textContent = count;
            byId.style.display = count > 0 ? 'flex' : 'none';
        }
        /* cache for next page load */
        localStorage.setItem('bazar_unread_count', count);
    }

    function updateMsgCount() {
        var uid = localStorage.getItem('bazar_firebase_uid') || '';
        if (!uid) return;

        /* Show cached count immediately, then refresh from API */
        var cached = parseInt(localStorage.getItem('bazar_unread_count') || '0', 10);
        if (cached > 0) setMsgBadge(cached);

        fetch('/api/chat/convs?uid=' + encodeURIComponent(uid))
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

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', updateHeader);
    } else {
        updateHeader();
    }
})();
