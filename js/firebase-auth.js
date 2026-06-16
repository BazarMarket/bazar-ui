window.BAZAR_API = (window.location.hostname === 'www.bazar.uk')
    ? 'https://admin.bazar.uk/api'
    : '/api';

var firebaseConfig = {
    apiKey: "AIzaSyDoE8UOGnc4IXprZG-TEce514JI1cwo0Z4",
    authDomain: "bazar-code-auth.firebaseapp.com",
    projectId: "bazar-code-auth",
    storageBucket: "bazar-code-auth.firebasestorage.app",
    messagingSenderId: "1065826568544",
    appId: "1:1065826568544:web:f573e9e85dd9fab9483605"
};
firebase.initializeApp(firebaseConfig);
var auth = firebase.auth();
var confirmationResult = null;
var recaptchaVerifier = null;
var modalMode = 'create'; // 'create' | 'login' | 'post-ad'

var _isTestEnv = (window.location.hostname === 'localhost' ||
    window.location.hostname.endsWith('.replit.dev') ||
    window.location.hostname.endsWith('.repl.co'));

if (_isTestEnv) {
    auth.settings.appVerificationDisabledForTesting = true;
}

function setupRecaptcha() {
    if (recaptchaVerifier) return;
    if (_isTestEnv) {
        // Mock verifier for test env — avoids reCAPTCHA API calls entirely
        recaptchaVerifier = {
            type: 'recaptcha',
            verify: function() { return Promise.resolve('test-token'); },
            render: function() { return Promise.resolve(0); },
            _reset: function() {},
            clear: function() {}
        };
        return;
    }
    try {
        var container = document.getElementById('recaptcha-container');
        if (container) container.innerHTML = '';
        recaptchaVerifier = new firebase.auth.RecaptchaVerifier('recaptcha-container', {
            size: 'invisible',
            callback: function() {}
        });
    } catch(e) {
        console.error('reCAPTCHA setup error:', e.code, e.message);
        if (window.bzLogError) window.bzLogError('firebase', 'reCAPTCHA setup: ' + (e.code || e.message));
        recaptchaVerifier = null;
    }
}

function switchRentType(type, btn) {
    btn.closest('.rent-toggle__btns').querySelectorAll('.rent-toggle__btn').forEach(function(b) {
        b.classList.remove('active');
    });
    btn.classList.add('active');
    document.getElementById('rent-long').style.display = type === 'long' ? '' : 'none';
    document.getElementById('rent-short').style.display = type === 'short' ? '' : 'none';
    var showAll = document.getElementById('rent-show-all');
    if (showAll) {
        showAll.href = type === 'short' ? '/property-short-rent' : '/property-to-rent';
    }
}

function switchJobType(type, btn) {
    btn.closest('.rent-toggle__btns').querySelectorAll('.rent-toggle__btn').forEach(function(b) {
        b.classList.remove('active');
    });
    btn.classList.add('active');
    document.getElementById('jobs-vacancy').style.display = type === 'vacancy' ? '' : 'none';
    document.getElementById('jobs-seeking').style.display = type === 'seeking' ? '' : 'none';
}

function switchMotorsRentType(type, btn) {
    btn.closest('.rent-toggle__btns').querySelectorAll('.rent-toggle__btn').forEach(function(b) {
        b.classList.remove('active');
    });
    btn.classList.add('active');
    document.getElementById('motors-rent-long').style.display = type === 'long' ? '' : 'none';
    document.getElementById('motors-rent-short').style.display = type === 'short' ? '' : 'none';
}

function doLogin() {
    var nameEl = document.getElementById('header-username');
    if (nameEl) nameEl.textContent = localStorage.getItem('bazar_username') || '';
    var gender = localStorage.getItem('bazar_gender') || 'male';
    var avatarEl = document.getElementById('header-avatar');
    if (avatarEl) {
        var avatarImg = avatarEl.querySelector('img') || avatarEl;
        if (avatarImg && avatarImg.tagName === 'IMG') {
            var savedAv = localStorage.getItem('bazar_avatar');
            avatarImg.src = savedAv || (gender === 'female' ? 'icon/woman.png' : 'icon/man.svg');
        }
    }
    var phoneMenuEl = document.getElementById('header-menu-phone');
    if (phoneMenuEl) phoneMenuEl.textContent = localStorage.getItem('bazar_phone') || '';
    var _hg = document.getElementById('header-guest');
    var _hl = document.getElementById('header-logged-in');
    if (_hg) _hg.style.display = 'none';
    if (_hl) _hl.style.display = '';
    document.body.classList.add('bazar-logged');
    /* Fetch fresh avatar from API and save to localStorage so it persists across pages */
    var _loginUid = localStorage.getItem('bazar_firebase_uid');
    if (_loginUid && !localStorage.getItem('bazar_avatar')) {
        var _api = (window.BAZAR_API || (window.location.hostname === 'www.bazar.uk' ? 'https://admin.bazar.uk/api' : '/api'));
        fetch(_api + '/customers/' + encodeURIComponent(_loginUid))
            .then(function(r) { return r.ok ? r.json() : {}; })
            .then(function(d) {
                if (d.avatar) {
                    try { localStorage.setItem('bazar_avatar', d.avatar); } catch(ex) {}
                    var _avEl = document.getElementById('header-avatar');
                    if (_avEl) {
                        var _avImg = _avEl.querySelector('img') || (_avEl.tagName === 'IMG' ? _avEl : null);
                        if (_avImg) _avImg.src = d.avatar;
                    }
                }
            }).catch(function() {});
    }
    /* Post-ad page: re-fill Contact Details with registered name/phone */
    if (window._bazarPostAdLockContact) window._bazarPostAdLockContact();
}

function syncFavoritesFromServer(uid) {
    fetch('/api/favorites?uid=' + encodeURIComponent(uid))
        .then(function(r) { return r.ok ? r.json() : null; })
        .then(function(data) {
            if (!data || !data.ids) return;
            var toDelete = [];
            for (var i = 0; i < localStorage.length; i++) {
                var k = localStorage.key(i);
                if (k && k.indexOf('favorite_') === 0) toDelete.push(k);
            }
            toDelete.forEach(function(k) { localStorage.removeItem(k); });
            data.ids.forEach(function(id) { localStorage.setItem('favorite_' + id, '1'); });
            if (window.updateFavCount) window.updateFavCount();
        })
        .catch(function() {});
}
window.syncFavoritesFromServer = syncFavoritesFromServer;

function uploadLocalFavoritesToServer(uid) {
    for (var i = 0; i < localStorage.length; i++) {
        var k = localStorage.key(i);
        if (k && k.indexOf('favorite_') === 0 && localStorage.getItem(k) === '1') {
            var pid = parseInt(k.replace('favorite_', ''), 10);
            if (pid) {
                (function(_pid) {
                    fetch('/api/favorites', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({uid: uid, property_id: _pid, active: 1})
                    }).catch(function() {});
                })(pid);
            }
        }
    }
}
window.uploadLocalFavoritesToServer = uploadLocalFavoritesToServer;

function clearUserLocalData() {
    localStorage.removeItem('bazar_username');
    localStorage.removeItem('bazar_phone');
    localStorage.removeItem('bazar_gender');
    localStorage.removeItem('bazar_plan');
    localStorage.removeItem('bazar_firebase_uid');
    /* favorites (favorite_*) are intentionally kept in localStorage across sessions */
}

function resetRecaptcha() {
    try { if (recaptchaVerifier) { recaptchaVerifier.clear(); } } catch(e) {}
    recaptchaVerifier = null;
    var c = document.getElementById('recaptcha-container');
    if (c) c.innerHTML = '';
}

function doLogout() {
    clearUserLocalData();
    auth.signOut();
    resetRecaptcha();
    var nameEl = document.getElementById('header-username');
    if (nameEl) nameEl.textContent = '';
    var guestEl = document.getElementById('header-guest');
    var loggedEl = document.getElementById('header-logged-in');
    if (loggedEl) loggedEl.style.display = 'none';
    if (guestEl) guestEl.style.display = '';
    document.body.classList.remove('bazar-logged');
}

function openLoginModal() {
    modalMode = 'login';
    resetRecaptcha();
    document.querySelector('#createAccountModal .modal-title').textContent = 'Login / Register';
    document.getElementById('createAccountModal').classList.add('modal-overlay--active');
    document.body.style.overflow = 'hidden';
}

function handleLogin() {
    var h = window.location.hostname;
    if (h === 'www.bazar.uk' || h === 'bazar.uk') {
        openLoginModal();
    } else {
        doLogin();
    }
}

function normalizeUkPhoneRealtime(e) {
    var input = e.target;
    var pos = input.selectionStart;
    var raw = input.value.replace(/[^\d+]/g, '');
    if (raw.startsWith('+44')) raw = raw.slice(3);
    else if (raw.startsWith('0044')) raw = raw.slice(4);
    else if (raw.startsWith('44') && raw.length >= 12) raw = raw.slice(2);
    else if (raw.startsWith('0')) raw = raw.slice(1);
    raw = raw.slice(0, 10);
    var formatted = raw;
    if (raw.length > 7) formatted = raw.slice(0, 4) + ' ' + raw.slice(4, 7) + ' ' + raw.slice(7);
    else if (raw.length > 4) formatted = raw.slice(0, 4) + ' ' + raw.slice(4);
    input.value = formatted;
    var newLen = formatted.length;
    try { input.setSelectionRange(newLen, newLen); } catch(err) {}
}

function openCreateAccountModal() {
    modalMode = 'create';
    document.querySelector('#createAccountModal .modal-title').textContent = 'Login / Register';
    document.getElementById('createAccountModal').classList.add('modal-overlay--active');
    document.body.style.overflow = 'hidden';
    var inp = document.querySelector('.modal-number-input');
    if (inp) {
        inp.value = '';
        inp.removeEventListener('input', normalizeUkPhoneRealtime);
        inp.addEventListener('input', normalizeUkPhoneRealtime);
        setTimeout(function() { inp.focus(); }, 100);
    }
}

function openPostAdModal() {
    modalMode = 'post-ad';
    document.querySelector('#createAccountModal .modal-title').textContent = 'Post an Ad';
    document.getElementById('createAccountModal').classList.add('modal-overlay--active');
    document.body.style.overflow = 'hidden';
    var inp = document.querySelector('.modal-number-input');
    if (inp) {
        inp.value = '';
        inp.removeEventListener('input', normalizeUkPhoneRealtime);
        inp.addEventListener('input', normalizeUkPhoneRealtime);
        setTimeout(function() { inp.focus(); }, 100);
    }
}

function handlePostAd(e) {
    /* post-ad.html now handles its own auth — always navigate directly */
    return true;
}

function switchToLogin() {
    closeOtpModal();
    var errEl = document.getElementById('otpError');
    if (errEl) { errEl.style.display = 'none'; errEl.innerHTML = ''; }
    openLoginModal();
}

function closeCreateAccountModal() {
    document.getElementById('createAccountModal').classList.remove('modal-overlay--active');
    document.body.style.overflow = '';
}

function closeModalOutside(e) {
    if (e.target === document.getElementById('createAccountModal')) closeCreateAccountModal();
}

function toggleSignBtns(checkbox) {
    var btns = document.querySelectorAll('#modalSignBtns .modal-btn');
    btns.forEach(function(btn) {
        if (checkbox.checked) {
            btn.classList.remove('modal-btn--gray');
            btn.classList.add('modal-btn--orange');
        } else {
            btn.classList.remove('modal-btn--orange');
            btn.classList.add('modal-btn--gray');
        }
    });
}

var otpTimerInterval = null;
var otpResendCount = 0;
var _bazarOtpPhone = '';

function showPhoneError(msg, isHtml) {
    var input = document.querySelector('.modal-number-input');
    if (!input) {
        /* Post-ad context: show error near sellerPhoneInput instead */
        var paErr = document.getElementById('sellerPhoneError');
        if (paErr) { paErr.textContent = msg; paErr.style.display = 'block'; paErr.scrollIntoView({ behavior: 'smooth', block: 'center' }); }
        return;
    }
    var err = document.getElementById('phoneError');
    if (!err) {
        err = document.createElement('p');
        err.id = 'phoneError';
        err.style.cssText = 'color:#e53935;font-size:13px;margin:4px 0 8px;display:none';
        var wrap = input.closest('.modal-phone-input');
        if (wrap && wrap.after) { wrap.after(err); } else { input.parentNode.parentNode.insertBefore(err, input.parentNode.nextSibling); }
    }
    if (isHtml) { err.innerHTML = msg; } else { err.textContent = msg; }
    err.style.display = 'block';
}

function clearPhoneError() {
    var err = document.getElementById('phoneError');
    if (err) err.style.display = 'none';
}

function doSendFirebaseSms(phoneNumber, smsBtn) {
    if (!recaptchaVerifier) {
        setupRecaptcha();
        if (!recaptchaVerifier) {
            showPhoneError('Could not initialize verification. Please reload the page and try again.');
            smsBtn.textContent = 'Sign in by an SMS';
            smsBtn.disabled = false;
            return;
        }
    }
    auth.signInWithPhoneNumber(phoneNumber, recaptchaVerifier)
        .then(function(result) {
            confirmationResult = result;
            smsBtn.textContent = 'Sign in by an SMS';
            smsBtn.disabled = false;
            if (window.bzLogError) window.bzLogError('firebase', 'SMS sent OK / ' + phoneNumber, null, phoneNumber);
            openOtpModal(phoneNumber);
        })
        .catch(function(error) {
            console.error('SMS error code:', error.code, 'message:', error.message);
            if (window.bzLogError) window.bzLogError('firebase', 'SMS send: ' + (error.code || error.message) + ' / ' + phoneNumber, null, phoneNumber);
            smsBtn.textContent = 'Sign in by an SMS';
            smsBtn.disabled = false;
            if (error.code === 'auth/invalid-phone-number') {
                showPhoneError('Invalid phone number. Please check and try again.');
            } else if (error.code === 'auth/too-many-requests') {
                showPhoneError('Too many attempts. Please try again later.');
            } else if (error.code === 'auth/captcha-check-failed') {
                showPhoneError('reCAPTCHA failed. Please reload the page and try again.');
            } else if (error.code === 'auth/quota-exceeded') {
                showPhoneError('SMS quota exceeded. Please try again tomorrow.');
            } else {
                showPhoneError('Error (' + (error.code || 'unknown') + '). Please reload and try again.');
            }
            try { if (recaptchaVerifier) { recaptchaVerifier.clear(); } } catch(e) {}
            recaptchaVerifier = null;
            var c = document.getElementById('recaptcha-container');
            if (c) c.innerHTML = '';
            setupRecaptcha();
        });
}

function sendSmsCode() {
    var _agCb = document.getElementById('agreeCheckbox');
    if (_agCb && !_agCb.checked) { document.getElementById('agreeError').style.display = 'block'; return; }
    if (_agCb) document.getElementById('agreeError').style.display = 'none';
    clearPhoneError();
    var rawValue = document.querySelector('.modal-number-input').value.replace(/[\s\(\)\-_\.]/g, '');
    if (rawValue.startsWith('+44')) {
        rawValue = rawValue.slice(3);
    } else if (rawValue.startsWith('0044')) {
        rawValue = rawValue.slice(4);
    } else if (rawValue.startsWith('44') && rawValue.length >= 12) {
        rawValue = rawValue.slice(2);
    } else if (rawValue.startsWith('0')) {
        rawValue = rawValue.slice(1);
    }
    if (!rawValue || rawValue.length < 9 || rawValue.length > 11) {
        showPhoneError('Please enter a valid UK phone number');
        return;
    }
    var phoneNumber = '+44' + rawValue;

    var smsBtn = document.querySelector('#modalSignBtns .modal-btn:first-child');
    smsBtn.textContent = 'Sending...';
    smsBtn.disabled = true;
    doSendFirebaseSms(phoneNumber, smsBtn);
}

function openOtpModal(phoneNumber) {
    var cleanNum = phoneNumber || '+44' + document.querySelector('.modal-number-input').value.replace(/[\s\(\)\-]/g, '');
    var display = cleanNum.replace(/(\+44)(\d{4})(\d{6})/, '$1 $2 $3');
    _bazarOtpPhone = cleanNum;
    otpResendCount = 0;
    document.getElementById('otpPhoneDisplay').textContent = display;
    document.getElementById('otpError').style.display = 'none';
    var _cam = document.getElementById('createAccountModal');
    if (_cam) _cam.classList.remove('modal-overlay--active');
    document.getElementById('otpModal').classList.add('modal-overlay--active');
    document.querySelectorAll('.otp-input').forEach(function(inp) { inp.value = ''; });
    document.querySelectorAll('.otp-input')[0].focus();
    var rb = document.getElementById('otpReportBtn');
    if (rb) rb.style.display = 'none';
    startOtpTimer();
}

function verifyOtpCode() {
    var code = '';
    document.querySelectorAll('.otp-input').forEach(function(inp) { code += inp.value; });
    if (code.length < 6 || !confirmationResult) return;

    confirmationResult.confirm(code)
        .then(function(result) {
            document.getElementById('otpError').style.display = 'none';
            var uid = result.user ? result.user.uid : null;
            var phone = result.user ? result.user.phoneNumber : null;

            // Очищаем старые данные другого пользователя (включая favorites)
            clearUserLocalData();

            if (phone) localStorage.setItem('bazar_phone', phone);
            if (uid)   localStorage.setItem('bazar_firebase_uid', uid);
            if (window.bzLogError) window.bzLogError('firebase', 'OTP verified OK / ' + (phone || uid), null, phone);

            // Проверяем: есть ли аккаунт в базе?
            fetch(window.BAZAR_API + '/customers/' + encodeURIComponent(uid))
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    if (data.exists) {
                        // Log in — загружаем данные и входим
                        localStorage.setItem('bazar_username', data.name);
                        localStorage.setItem('bazar_gender',   data.gender);
                        localStorage.setItem('bazar_plan',     data.plan || 'free');
                        closeOtpModal();
                        doLogin();
                        syncFavoritesFromServer(uid);
                        if (window.bzLogError) window.bzLogError('firebase', 'Login OK: ' + data.name + ' / ' + (phone || uid), null, phone);
                        if (window._postAdCallback) {
                            var _cb = window._postAdCallback;
                            window._postAdCallback = null;
                            _cb();
                        } else if (modalMode === 'post-ad') {
                            window.location.href = 'post-ad';
                        }
                    } else {
                        // Новый пользователь — показываем форму профиля
                        if (window.bzLogError) window.bzLogError('firebase', 'New user - profile form / ' + (phone || uid), null, phone);
                        openProfileModal(); // handles _postAdSellerName pre-fill internally
                    }
                })
                .catch(function(err) {
                    // Ошибка сети — показываем форму на всякий случай
                    if (window.bzLogError) window.bzLogError('firebase', 'Customer check failed: ' + (err && err.message ? err.message : 'network error'), null, _bazarOtpPhone);
                    openProfileModal();
                });
        })
        .catch(function(error) {
            console.error('Verify error:', error);
            if (window.bzLogError) window.bzLogError('firebase', 'OTP verify: ' + (error.code || error.message), null, _bazarOtpPhone);
            var errEl = document.getElementById('otpError');
            errEl.textContent = 'Wrong code. Please try again.';
            errEl.style.display = 'block';
            document.querySelectorAll('.otp-input').forEach(function(inp) { inp.value = ''; });
            document.querySelectorAll('.otp-input')[0].focus();
        });
}

function closeOtpModal() {
    document.getElementById('otpModal').classList.remove('modal-overlay--active');
    document.body.style.overflow = '';
    clearInterval(otpTimerInterval);
}

function closeOtpModalOutside(e) {
    if (e.target === document.getElementById('otpModal')) closeOtpModal();
}

function backToCreateAccount() {
    document.getElementById('otpModal').classList.remove('modal-overlay--active');
    document.body.style.overflow = '';
    clearInterval(otpTimerInterval);
    var createModal = document.getElementById('createAccountModal');
    if (createModal) createModal.classList.add('modal-overlay--active');
    // If no createAccountModal (post-ad page) — user just edits phone in the form
    if (window._postAdCallback) { window._postAdCallback = null; }
}

function startOtpTimer() {
    clearInterval(otpTimerInterval);
    var seconds = 60;
    var btn = document.getElementById('otpResendBtn');
    var timerEl = document.getElementById('otpTimer');
    btn.disabled = true;
    btn.innerHTML = 'Get new code: <span id="otpTimer">' + seconds + '</span> s.';
    timerEl = document.getElementById('otpTimer');
    otpTimerInterval = setInterval(function() {
        seconds--;
        timerEl.textContent = seconds;
        if (seconds <= 0) {
            clearInterval(otpTimerInterval);
            btn.disabled = false;
            btn.textContent = 'Get new code';
            btn.onclick = function() { sendSmsCode(); };
            var rb = document.getElementById('otpReportBtn');
            if (rb) rb.style.display = 'block';
        }
    }, 1000);
}

function reportSmsIssue() {
    var btn = document.getElementById('otpReportBtn');
    if (btn) { btn.disabled = true; btn.textContent = 'Reported. We\'ll check it.'; }
    fetch((window.BAZAR_API || '/api') + '/sms-report', {
        method: 'POST',
        headers: {'Content-Type':'application/json','Accept':'application/json'},
        body: JSON.stringify({ phone: _bazarOtpPhone })
    }).catch(function() {});
}

var selectedGender = 'male';

function selectGender(gender) {
    selectedGender = gender;
    document.getElementById('profileAvatarPreview').src = gender === 'female' ? 'icon/woman.png' : 'icon/man.png';
    document.getElementById('genderMale').classList.toggle('profile-gender-btn--active', gender === 'male');
    document.getElementById('genderFemale').classList.toggle('profile-gender-btn--active', gender === 'female');
    checkProfileReady();
}

function checkProfileReady() {
    var name = document.getElementById('profileFullName').value.trim();
    var btn = document.getElementById('profileSubmitBtn');
    if (name && selectedGender) {
        btn.classList.remove('profile-submit-btn--gray');
    } else {
        btn.classList.add('profile-submit-btn--gray');
    }
}

function openProfileModal() {
    selectedGender = 'male';
    document.getElementById('profileAvatarPreview').src = 'icon/man.png';
    document.getElementById('genderMale').classList.add('profile-gender-btn--active');
    document.getElementById('genderFemale').classList.remove('profile-gender-btn--active');
    var nameInp = document.getElementById('profileFullName');
    if (nameInp) {
        if (window._postAdSellerName) {
            /* Post-ad flow: name already filled in Contact Details — pre-fill and hide */
            nameInp.value = window._postAdSellerName;
            nameInp.style.display = 'none';
        } else {
            nameInp.value = '';
            nameInp.style.display = '';
        }
    }
    document.getElementById('profileSubmitBtn').classList.add('profile-submit-btn--gray');
    document.getElementById('otpModal').classList.remove('modal-overlay--active');
    document.getElementById('profileModal').classList.add('modal-overlay--active');
    checkProfileReady();
}

function closeProfileModal() {
    document.getElementById('profileModal').classList.remove('modal-overlay--active');
    document.body.style.overflow = '';
}

function finishRegistration() {
    var name = document.getElementById('profileFullName').value.trim();
    if (!name || !selectedGender) return;
    localStorage.setItem('bazar_username', name);
    localStorage.setItem('bazar_gender', selectedGender);
    if (!localStorage.getItem('bazar_plan')) localStorage.setItem('bazar_plan', 'free');
    var isPostAd = (modalMode === 'post-ad');
    closeProfileModal();
    doLogin();
    if (typeof gtag === 'function') gtag('event', 'conversion', {'send_to': 'AW-1808636054/PRn-CPy5m5scEN_rn7BD'});
    var _regPhone = (function(){ try { return localStorage.getItem('bazar_phone') || ''; } catch(e){ return ''; } })();
    if (window.bzLogError) window.bzLogError('firebase', 'Registration complete: ' + name, null, _regPhone);

    var firebaseUser = auth.currentUser;
    var uid   = (firebaseUser && firebaseUser.uid) ? firebaseUser.uid : localStorage.getItem('bazar_firebase_uid');
    var phone = (firebaseUser && firebaseUser.phoneNumber) ? firebaseUser.phoneNumber : (localStorage.getItem('bazar_phone') || '');
    if (firebaseUser && firebaseUser.uid) {
        localStorage.setItem('bazar_firebase_uid', firebaseUser.uid);
    }
    /* Save customer — store promise so post-ad flow can await it before page navigation */
    var _customerSaveP = Promise.resolve();
    if (uid) {
        uploadLocalFavoritesToServer(uid);
        _customerSaveP = fetch(window.BAZAR_API + '/customers', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
            body: JSON.stringify({
                firebase_uid: uid,
                phone: phone,
                name: name,
                gender: selectedGender,
                plan: localStorage.getItem('bazar_plan') || 'free',
            })
        }).catch(function(err) {
            if (window.bzLogError) window.bzLogError('firebase', 'Customer create failed: ' + (err && err.message ? err.message : 'network error'), null, phone);
        });

        /* Save gender to server.py's authoritative SQLite DB so ALL pages show correct avatar */
        fetch('/api/save-gender', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ uid: uid, gender: selectedGender })
        }).catch(function() {});
    }

    if (window._postAdCallback) {
        var _postCb = window._postAdCallback;
        window._postAdCallback = null;
        window._postAdSellerName = null;
        /* Wait for customer to be saved in DB before navigating away */
        _customerSaveP.then(function() { _postCb(); });
        return;
    }
    if (isPostAd) {
        window.location.href = 'post-ad';
    }
}

/* ── Post-Ad Auth: send OTP using phone from Contact Details form ── */
window.bzSendSmsFromPostAd = function(phoneNumber, callback) {
    window._postAdCallback = callback;
    setupRecaptcha();
    var fakeBtn = { textContent: '', disabled: false };
    doSendFirebaseSms(phoneNumber, fakeBtn);
};


document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        closeCreateAccountModal();
        closeOtpModal();
        closeProfileModal();
    }
});

document.addEventListener('DOMContentLoaded', function() {
    var h = window.location.hostname;
    var isProduction = (h === 'www.bazar.uk' || h === 'bazar.uk');

    if (!isProduction) {
        // DEV / Replit — автологин с дефолтными данными
        if (!localStorage.getItem('bazar_username')) {
            localStorage.setItem('bazar_username',    'Andreas Xenofontos');
            localStorage.setItem('bazar_gender',      'male');
            localStorage.setItem('bazar_firebase_uid','test_uid_123');
            if (!localStorage.getItem('bazar_plan'))  localStorage.setItem('bazar_plan', 'free');
        }
        doLogin();
    } else {
        // Production — восстанавливаем сессию если пользователь уже логинился
        if (localStorage.getItem('bazar_username')) {
            doLogin();
            var _restoreUid = localStorage.getItem('bazar_firebase_uid');
            if (_restoreUid) syncFavoritesFromServer(_restoreUid);
        }
    }

    var otpInputs = document.querySelectorAll('.otp-input');
    otpInputs.forEach(function(input, index) {
        input.addEventListener('input', function() {
            this.value = this.value.replace(/[^0-9]/g, '');
            if (this.value && index < otpInputs.length - 1) {
                otpInputs[index + 1].focus();
            }
            if (this.value && index === otpInputs.length - 1) {
                verifyOtpCode();
            }
        });
        input.addEventListener('keydown', function(e) {
            if (e.key === 'Backspace' && !this.value && index > 0) {
                otpInputs[index - 1].focus();
            }
        });
    });
});
