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
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', updateHeader);
    } else {
        updateHeader();
    }
})();
