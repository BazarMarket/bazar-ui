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

function setupRecaptcha() {
    try {
        if (recaptchaVerifier) {
            recaptchaVerifier.clear();
            recaptchaVerifier = null;
        }
        recaptchaVerifier = new firebase.auth.RecaptchaVerifier('recaptcha-container', {
            size: 'invisible',
            callback: function() {}
        });
        recaptchaVerifier.render().catch(function(e) {
            console.error('reCAPTCHA render error:', e.code, e.message);
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
}

function doLogin() {
    document.getElementById('header-guest').style.display = 'none';
    document.getElementById('header-logged-in').style.display = '';
}

function doLogout() {
    auth.signOut();
    document.getElementById('header-logged-in').style.display = 'none';
    document.getElementById('header-guest').style.display = '';
}

function openCreateAccountModal() {
    document.getElementById('createAccountModal').classList.add('modal-overlay--active');
    document.body.style.overflow = 'hidden';
    setupRecaptcha();
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

function sendSmsCode() {
    if (!document.getElementById('agreeCheckbox').checked) { document.getElementById('agreeError').style.display = 'block'; return; }
    document.getElementById('agreeError').style.display = 'none';
    var rawValue = document.querySelector('.modal-number-input').value.replace(/[\s\(\)\-_]/g, '');
    if (!rawValue || rawValue.length < 10) { alert('Please enter your phone number'); return; }
    var phoneNumber = '+44' + rawValue;

    if (!recaptchaVerifier) {
        setupRecaptcha();
        if (!recaptchaVerifier) {
            alert('Could not initialize verification. Please reload the page and try again. (Debug: check console for details)');
            return;
        }
    }

    var smsBtn = document.querySelector('#modalSignBtns .modal-btn:first-child');
    smsBtn.textContent = 'Sending...';
    smsBtn.disabled = true;

    auth.signInWithPhoneNumber(phoneNumber, recaptchaVerifier)
        .then(function(result) {
            confirmationResult = result;
            smsBtn.textContent = 'Sign in by an SMS';
            smsBtn.disabled = false;
            openOtpModal(phoneNumber);
        })
        .catch(function(error) {
            console.error('SMS error:', error);
            smsBtn.textContent = 'Sign in by an SMS';
            smsBtn.disabled = false;
            if (error.code === 'auth/invalid-phone-number') {
                alert('Invalid phone number. Please check and try again.');
            } else if (error.code === 'auth/too-many-requests') {
                alert('Too many attempts. Please try again later.');
            } else {
                alert('Error sending SMS: ' + error.message);
            }
            recaptchaVerifier = null;
            setupRecaptcha();
        });
}

function openOtpModal(phoneNumber) {
    var cleanNum = phoneNumber || '+44' + document.querySelector('.modal-number-input').value.replace(/[\s\(\)\-]/g, '');
    var display = cleanNum.replace(/(\+44)(\d{4})(\d{6})/, '$1 $2 $3');
    document.getElementById('otpPhoneDisplay').textContent = display;
    document.getElementById('otpError').style.display = 'none';
    document.getElementById('createAccountModal').classList.remove('modal-overlay--active');
    document.getElementById('otpModal').classList.add('modal-overlay--active');
    document.querySelectorAll('.otp-input').forEach(function(inp) { inp.value = ''; });
    document.querySelectorAll('.otp-input')[0].focus();
    startOtpTimer();
}

function verifyOtpCode() {
    var code = '';
    document.querySelectorAll('.otp-input').forEach(function(inp) { code += inp.value; });
    if (code.length < 6 || !confirmationResult) return;

    confirmationResult.confirm(code)
        .then(function(result) {
            document.getElementById('otpError').style.display = 'none';
            openProfileModal();
        })
        .catch(function(error) {
            console.error('Verify error:', error);
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
    document.getElementById('createAccountModal').classList.add('modal-overlay--active');
    clearInterval(otpTimerInterval);
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
        }
    }, 1000);
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
    document.getElementById('header-username').textContent = name;
    document.getElementById('header-avatar').src = selectedGender === 'female' ? 'icon/woman.png' : 'icon/man.svg';
    closeProfileModal();
    doLogin();
}

document.addEventListener('DOMContentLoaded', function() {
    setupRecaptcha();
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
