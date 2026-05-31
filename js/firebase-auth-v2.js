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
            var savedAvatar = localStorage.getItem('bazar_avatar');
            avatarImg.src = savedAvatar || (gender === 'female' ? '/icon/woman.png' : '/icon/man.svg');
        }
    }
    var phoneMenuEl = document.getElementById('header-menu-phone');
    if (phoneMenuEl) phoneMenuEl.textContent = localStorage.getItem('bazar_phone') || '';
    document.getElementById('header-guest').style.display = 'none';
    document.getElementById('header-logged-in').style.display = '';
    document.body.classList.add('bazar-logged');
}

function clearUserLocalData() {
    var toDelete = [];
    for (var i = 0; i < localStorage.length; i++) {
        var k = localStorage.key(i);
        if (k && (k.indexOf('bazar_') === 0 || k.indexOf('favorite_') === 0)) {
            toDelete.push(k);
        }
    }
    toDelete.forEach(function(k) { localStorage.removeItem(k); });
}

window.addEventListener('pageshow', function(e) {
    if (e.persisted && !localStorage.getItem('bazar_firebase_uid')) {
        doLogout();
    }
});

function doLogout() {
    clearUserLocalData();
    auth.signOut();
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
    if (!input) return;
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
            openOtpModal(phoneNumber);
        })
        .catch(function(error) {
            console.error('SMS error code:', error.code, 'message:', error.message);
            if (window.bzLogError) window.bzLogError('firebase', 'SMS send: ' + (error.code || error.message));
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
    document.getElementById('createAccountModal').classList.remove('modal-overlay--active');
    document.getElementById('otpModal').classList.add('modal-overlay--active');
    document.querySelectorAll('.otp-input').forEach(function(inp) { inp.value = ''; });
    document.querySelectorAll('.otp-input')[0].focus({ preventScroll: true });
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

            // Проверяем: есть ли аккаунт в базе?
            function handleCustomerData(data) {
                if (data.exists) {
                    if (modalMode === 'post-ad') {
                        localStorage.setItem('bazar_username', data.name);
                        localStorage.setItem('bazar_gender',   data.gender);
                        localStorage.setItem('bazar_plan',     data.plan || 'free');
                        if (data.avatar) localStorage.setItem('bazar_avatar', data.avatar);
                        closeOtpModal();
                        doLogin();
                        window.location.href = 'post-ad';
                    } else {
                        localStorage.setItem('bazar_username', data.name);
                        localStorage.setItem('bazar_gender',   data.gender);
                        localStorage.setItem('bazar_plan',     data.plan || 'free');
                        if (data.avatar) localStorage.setItem('bazar_avatar', data.avatar);
                        closeOtpModal();
                        doLogin();
                    }
                } else {
                    // Новый пользователь — показываем форму профиля
                    openProfileModal();
                }
            }
            function showNetworkError() {
                var errEl = document.getElementById('otpError');
                if (errEl) {
                    errEl.textContent = 'Connection error. Please check your internet and try again.';
                    errEl.style.display = 'block';
                }
                document.querySelectorAll('.otp-input').forEach(function(inp) { inp.value = ''; });
                var firstInp = document.querySelectorAll('.otp-input')[0];
                if (firstInp) firstInp.focus({ preventScroll: true });
            }
            fetch(window.BAZAR_API + '/customers/' + encodeURIComponent(uid))
                .then(function(r) { return r.json(); })
                .then(handleCustomerData)
                .catch(function() {
                    // Ошибка сети — повторяем один раз через 2 сек
                    setTimeout(function() {
                        fetch(window.BAZAR_API + '/customers/' + encodeURIComponent(uid))
                            .then(function(r) { return r.json(); })
                            .then(handleCustomerData)
                            .catch(showNetworkError);
                    }, 2000);
                });
        })
        .catch(function(error) {
            console.error('Verify error:', error);
            if (window.bzLogError) window.bzLogError('firebase', 'OTP verify: ' + (error.code || error.message));
            var errEl = document.getElementById('otpError');
            errEl.textContent = 'Wrong code. Please try again.';
            errEl.style.display = 'block';
            document.querySelectorAll('.otp-input').forEach(function(inp) { inp.value = ''; });
            document.querySelectorAll('.otp-input')[0].focus({ preventScroll: true });
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
    document.getElementById('createAccountModal').classList.add('modal-overlay--active');
    clearInterval(otpTimerInterval);
}

function resendOtpCode() {
    var phoneDisplay = (document.getElementById('otpPhoneDisplay').textContent || '').replace(/\s/g, '');
    if (!phoneDisplay) return;

    var btn = document.getElementById('otpResendBtn');
    btn.disabled = true;
    btn.textContent = 'Sending...';
    document.getElementById('otpError').style.display = 'none';

    try { if (recaptchaVerifier) { recaptchaVerifier.clear(); } } catch(e) {}
    recaptchaVerifier = null;
    var c = document.getElementById('recaptcha-container');
    if (c) c.innerHTML = '';
    setupRecaptcha();

    auth.signInWithPhoneNumber(phoneDisplay, recaptchaVerifier)
        .then(function(result) {
            confirmationResult = result;
            document.querySelectorAll('.otp-input').forEach(function(inp) { inp.value = ''; });
            document.querySelectorAll('.otp-input')[0].focus({ preventScroll: true });
            startOtpTimer();
        })
        .catch(function(error) {
            console.error('Resend SMS error:', error.code, error.message);
            var errEl = document.getElementById('otpError');
            if (error.code === 'auth/too-many-requests') {
                errEl.textContent = 'Too many attempts. Please try again later.';
            } else {
                errEl.textContent = 'Failed to send code (' + (error.code || 'unknown') + '). Please try again.';
            }
            errEl.style.display = 'block';
            btn.disabled = false;
            btn.textContent = 'Get new code';
            try { if (recaptchaVerifier) { recaptchaVerifier.clear(); } } catch(e) {}
            recaptchaVerifier = null;
            if (c) c.innerHTML = '';
            setupRecaptcha();
        });
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
            btn.onclick = function() { resendOtpCode(); };
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
    document.getElementById('profileAvatarPreview').src = gender === 'female' ? '/icon/woman.png' : '/icon/man.png';
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
    document.getElementById('profileAvatarPreview').src = '/icon/man.png';
    document.getElementById('genderMale').classList.add('profile-gender-btn--active');
    document.getElementById('genderFemale').classList.remove('profile-gender-btn--active');
    document.getElementById('profileFullName').value = '';
    document.getElementById('profileSubmitBtn').classList.add('profile-submit-btn--gray');
    document.getElementById('otpModal').classList.remove('modal-overlay--active');
    document.getElementById('profileModal').classList.add('modal-overlay--active');
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
    localStorage.setItem('bazar_plan', 'free');
    var isPostAd = (modalMode === 'post-ad');
    closeProfileModal();
    doLogin();
    if (typeof gtag === 'function') gtag('event', 'conversion', {'send_to': 'AW-1808636054/PRn-CPy5m5scEN_rn7BD'});

    var firebaseUser = auth.currentUser;
    var uid   = (firebaseUser && firebaseUser.uid) ? firebaseUser.uid : localStorage.getItem('bazar_firebase_uid');
    var phone = (firebaseUser && firebaseUser.phoneNumber) ? firebaseUser.phoneNumber : (localStorage.getItem('bazar_phone') || '');
    if (firebaseUser && firebaseUser.uid) {
        localStorage.setItem('bazar_firebase_uid', firebaseUser.uid);
    }
    if (uid) {
        fetch(window.BAZAR_API + '/customers', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
            body: JSON.stringify({
                firebase_uid: uid,
                phone: phone,
                name: name,
                gender: selectedGender,
                plan: localStorage.getItem('bazar_plan') || 'free',
            })
        }).catch(function() {});

        /* Save gender to server.py's authoritative SQLite DB so ALL pages show correct avatar */
        fetch('/api/save-gender', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ uid: uid, gender: selectedGender })
        }).catch(function() {});
    }

    if (isPostAd) {
        window.location.href = 'post-ad';
    }
}


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
        }
    }

    setupRecaptcha();
    var otpInputs = document.querySelectorAll('.otp-input');
    otpInputs.forEach(function(input, index) {
        input.addEventListener('input', function() {
            this.value = this.value.replace(/[^0-9]/g, '');
            if (this.value && index < otpInputs.length - 1) {
                otpInputs[index + 1].focus({ preventScroll: true });
            }
            if (this.value && index === otpInputs.length - 1) {
                verifyOtpCode();
            }
        });
        input.addEventListener('keydown', function(e) {
            if (e.key === 'Backspace' && !this.value && index > 0) {
                otpInputs[index - 1].focus({ preventScroll: true });
            }
        });
    });
});
