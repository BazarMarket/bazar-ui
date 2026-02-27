window.onload = function () {


    // new AirDatepicker('#input');

    // ПРЕВЬЮ КАРТИНОК =============================================================================================================

    document.addEventListener('click', function (e) {

        // Клик по квадрату
        const box = e.target.closest('.image-upload__box');
        if (box) {
            const wrapper = box.closest('.image-upload');
            const input = wrapper.querySelector('.image-upload__input');
            const preview = wrapper.querySelector('.image-upload__preview');

            if (!preview.src) {
                input.click();
            }
        }

        // Клик по крестику
        const remove = e.target.closest('.image-upload__remove');
        if (remove) {
            e.stopPropagation();
            const wrapper = remove.closest('.image-upload');

            wrapper.querySelector('.image-upload__input').value = '';
            wrapper.querySelector('.image-upload__preview').src = '';
            wrapper.querySelector('.image-upload__preview').style.display = 'none';
            wrapper.querySelector('.image-upload__plus').style.display = 'flex';
            remove.style.display = 'none';
        }
    });

    // Обработка выбора файла
    document.addEventListener('change', function (e) {
        if (!e.target.classList.contains('image-upload__input')) return;

        const input = e.target;
        const wrapper = input.closest('.image-upload');
        const preview = wrapper.querySelector('.image-upload__preview');
        const plus = wrapper.querySelector('.image-upload__plus');
        const remove = wrapper.querySelector('.image-upload__remove');

        const file = input.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = () => {
            preview.src = reader.result;
            preview.style.display = 'block';
            plus.style.display = 'none';
            remove.style.display = 'block';
        };
        reader.readAsDataURL(file);
    });




    // ХЕДЕР ПРИ СКРОЛЛЕ =============================================================================================================


    const header = document.querySelector('.header');
    headerPosi();
    function headerPosi() {
        if (header) {

            let prevScrollpos = window.scrollY;
            document.addEventListener('scroll', () => {
                let currentScrollPos = window.scrollY;
                if (currentScrollPos > 0) {
                    header.classList.add('fixed');
                } else {
                    header.classList.remove('fixed');
                }
                if (currentScrollPos > 200) {
                    if (prevScrollpos >= currentScrollPos) {
                        header.style.top = "0";
                    } else {
                        header.style.top = - header.clientHeight + 'px';
                    }
                }
                prevScrollpos = currentScrollPos;
            });

        }
    }

    // ИНИЦИАЛИЗАЦИЯ СЛАЙДЕРОВ =============================================================================================================

    const sliderSlider = new Swiper('.slider-slider .swiper', {

        loop: true,
        watchOverflow: true,
        centerInsufficientSlides: true,
        autoHeight: true,
        slidesPerView: 3,
        spaceBetween: 10,


        // автопрокрутка
        // autoplay: {
        //     delay: 3000,
        //     disableOnInteraction: true,
        // },
        // effect: 'fade',
        // speed: 800,

        // навигация

        navigation: {
            prevEl: '.slider-slider .button-prev',
            nextEl: '.slider-slider .button-next',
        },
        pagination: {
            el: '.slider-slider .swiper-pagination',
            type: 'bullets',
            clickable: true,
        },


        // навигация мини-слайдером
        // thumbs: {
        //     swiper: {
        //         el: '.slider-mini .swiper',
        //         slidesPerView: 5,
        //         spaceBetween: 15,
        //         direction: 'vertical',
        //         watchOverflow: true,
        //         // loop: true,
        //     }
        // },

        // адаптация
        // breakpoints: {
        //     300: {
        //         slidesPerView: 1.4,
        //         spaceBetween: 10,
        //     },
        //     576: {
        //         slidesPerView: 2,
        //         spaceBetween: 10,
        //     },
        // }
    });


    const categoryMobSlider = new Swiper('.category-mob-slider .swiper', {

        // loop: true,
        watchOverflow: true,
        centerInsufficientSlides: true,
        // autoHeight: true,
        slidesPerView: 'auto',
        spaceBetween: 8,

    });

    const cardsSliders = new Swiper('.cards-sliders .swiper', {

        watchOverflow: true,
        centerInsufficientSlides: true,
        slidesPerView: 'auto',
        spaceBetween: 8,

    });

    const productGallery = new Swiper('.product-gallery .swiper', {
        loop: true,
        watchOverflow: true,
        centerInsufficientSlides: true,
        autoHeight: true,
        slidesPerView: 1,
        spaceBetween: 0,

        // автопрокрутка
        autoplay: {
            delay: 3000,
            disableOnInteraction: true,
        },
        effect: 'fade',
        speed: 800,

        pagination: {
            el: '.product-gallery .swiper-pagination',
            type: 'bullets',
            clickable: true,
        },

    });

    const sliderGalleryBig = new Swiper('.slider-gallery-big .swiper', {

        loop: true,
        watchOverflow: true,
        centerInsufficientSlides: true,
        autoHeight: true,
        slidesPerView: 1,
        spaceBetween: 10,




        // навигация

        navigation: {
            prevEl: '.slider-gallery-big .button-prev',
            nextEl: '.slider-gallery-big .button-next',
        },



        // навигация мини-слайдером
        thumbs: {
            swiper: {
                el: '.slider-gallery-mini .swiper',
                slidesPerView: 4,
                spaceBetween: 16,
                watchOverflow: true,
                loop: true,
            }
        },

        // адаптация
        // breakpoints: {
        //     300: {
        //         slidesPerView: 1.4,
        //         spaceBetween: 10,
        //     },
        //     576: {
        //         slidesPerView: 2,
        //         spaceBetween: 10,
        //     },
        // }
    });




    //ИНПУТ МАСКА ДЛЯ ТЕЛЕФОНА  =============================================================================================================
    const telInput = document.querySelectorAll('input[type="tel"]');
    var im = new Inputmask("38(999)999-99-99");
    im.mask(telInput);




    // СКРИПТ more ДЛЯ ТЕКСТА =============================================================================================================

    // Добавте блоку с текстом который необходимо скрывать клас ".more"
    // data-showChar="500" - количество видимых символов (поумолчанию 500)
    // data-ellipsestext="..." - текст перед кнопкой (поумолчанию ...) 
    // data-moretext="More" - текст на кнопке открыть (поумолчанию More) 
    // data-lesstext="Hide" - текст на кнопке закрыть (поумолчанию Hide) 


    const moreAll = document.querySelectorAll('.more');

    if (moreAll.length > 0) {
        moreActive();
        function moreActive() {
            moreAll.forEach(more => {
                let showChar = 500;
                if (more.hasAttribute('data-showChar')) {
                    showChar = Number(more.getAttribute('data-showChar'));
                }
                let ellipsestext = " ...";
                if (more.hasAttribute('data-ellipsestext')) {
                    ellipsestext = more.getAttribute('data-ellipsestext');
                }
                let moretext = "More";
                if (more.hasAttribute('data-moretext')) {
                    moretext = more.getAttribute('data-moretext');
                }
                let lesstext = "Hide";
                if (more.hasAttribute('data-lesstext')) {
                    lesstext = more.getAttribute('data-lesstext');
                }

                let content = more.innerHTML;

                if (content.length > showChar) {

                    content = String(content);

                    let contentSmall = content.substring(0, showChar);
                    let contentBig = content.substring(showChar, content.length);

                    content = contentSmall + '<span class="more__hide">' + contentBig + '</span>' + '<span class="more__ellips">' + ellipsestext + '</span>' + '<span class="more__link">' + moretext + '</span>';

                    more.innerHTML = content;

                    let moreLink = more.querySelector('.more__link');
                    let moreHide = more.querySelector('.more__hide');
                    let moreEllips = more.querySelector('.more__ellips');

                    moreHide.style.display = "none";

                    moreLink.addEventListener('click', () => {
                        if (more.classList.contains('active')) {
                            more.classList.remove('active');
                            moreHide.style.display = "none";
                            moreEllips.style.display = "inline";
                            moreLink.innerHTML = moretext;

                        } else {
                            more.classList.add('active');
                            moreHide.style.display = "inline";
                            moreEllips.style.display = "none";
                            moreLink.innerHTML = lesstext;
                        }
                    });
                }
            });
        }
    }





    // КАСТОМНЫЙ СЕЛЕКТ =============================================================================================================
    const castomSelect = () => {
        const elements = document.querySelectorAll('.castom-select');
        elements.forEach(el => {
            const choices = new Choices(el, {
                searchEnabled: false,
            });
        });

    }
    castomSelect();



    /* ТАБЫ =============================================================================================================
    Для работы табов, необходимо оборачивающему контейнеру задать класс '.mytab-js', для каждой кнопки атрибут 'data-tab-btn' с значением соответственного атрибута контента, а каждому блоку контента задать атрибут  'data-tab-content'
    Также в стилях нужно прописать стили для кнопок и конткнта с наличием и отсутсвием класса 'active' */

    /* Пример: */

    /*<div class="mytab-js">
        <div class="mytab__btn">
            <div data-tab-btn="tab1" class="active">Кнопка 1</div>
            <div data-tab-btn="tab2" class="">Кнопка 2</div>
        </div>
        <div class="tab-cusom-content">
            <div data-tab-content="tab1" class="active">Контенет 1</div>
            <div data-tab-content="tab2" class="">Контенет 2</div>
        </div>
    </div> */
    const myTab = document.querySelectorAll('.mytab-js');
    if (myTab.length > 0) {
        myTab.forEach(myTabItem => {
            let myTabItemBtn = myTabItem.querySelectorAll('[data-tab-btn]');
            let myTabItemContent = myTabItem.querySelectorAll('[data-tab-content]');

            myTabItemBtn.forEach(myTabItemBtnItem => {
                myTabItemBtnItem.addEventListener('click', () => {
                    myTabItemBtn.forEach(element => {
                        element.classList.remove('active');
                    });
                    myTabItemBtnItem.classList.add('active');
                    let myTabContentId = myTabItemBtnItem.getAttribute('data-tab-btn');

                    openTab(myTabContentId);
                });
            });

            function openTab(myTabContentId) {
                myTabItemContent.forEach(myTabItemContentItem => {
                    if (myTabItemContentItem.getAttribute('data-tab-content') == myTabContentId) {
                        myTabItemContent.forEach(element => {
                            element.classList.remove('active');
                        });
                        myTabItemContentItem.classList.add('active');
                    }
                });
            }
        });
    }
    /* end--------------------*/



    // БУРГЕР =============================================================================================================

    const openBtn = document.querySelectorAll('[data-open]');
    if (openBtn.length > 0) {
        openBtn.forEach(element => {
            element.addEventListener('click', () => {

                let openBodyId = element.getAttribute('data-open');
                let openBody = document.getElementById(openBodyId);
                let openBodyClass = '.' + openBody.classList[0];

                if (element.classList.contains('toggle-body-js')) {

                    element.classList.toggle('active');
                    if (element.classList.contains('active')) {
                        bodyOpen(openBody);
                    } else {
                        bodyClose(openBody);
                    }

                } else {
                    bodyOpen(openBody);
                }

                let closeBody = openBody.querySelector('.close-body-js')
                if (closeBody) {
                    closeBody.addEventListener('click', () => {
                        bodyClose(openBody);
                    });
                }

                document.addEventListener('click', function (e) {
                    if (!e.target.closest('[data-open]')) {
                        if (!e.target.closest(openBodyClass)) {
                            bodyClose(openBody);
                        }
                    }
                });
            });
        });

        function bodyClose(openBody) {
            openBody.classList.remove('active');
            bodyUnfixPosition();

            document.querySelectorAll('.toggle-body-js').forEach(element => {
                element.classList.remove('active');
            });

        }

        function bodyOpen(openBody) {
            openBody.classList.add('active');
            bodyFixPosition();
        }

        // Закрытие бургера по нажатию на ссылку

        const navLiAll = document.querySelectorAll('.navigation ul li');

        if (navLiAll.length > 0) {
            navLiAll.forEach(navLiItem => {
                navLiItem.addEventListener('click', () => {
                    let burger = document.querySelector('.burger-body')
                    bodyClose(burger);
                })
            });
        }

    }


    //  ЗАМЕНА ЗНАЧЕНИЯ ИНПУТОВ  +/-   =============================================================================================================
    const variableBlock = document.querySelectorAll('.variable-input');
    if (variableBlock.length > 0) {
        variableBlock.forEach(variableBlockItem => {
            variableBlockItem.addEventListener('click', (e) => {
                let variableInput = variableBlockItem.querySelector('.ipnut-number');
                if (e.target.closest('.btn-down')) {
                    if (variableInput.value > 1) {
                        variableInput.value--;
                    }
                }
                if (e.target.closest('.btn-up')) {
                    variableInput.value++;
                }
            })

        });

    }


    // РАЗВОРАЧИВАНИЕ ЭЛЕМЕНТОВ  =============================================================================================================
    const unfoldingButton = document.querySelectorAll('.unfolding');

    if (unfoldingButton.length > 0) {



        unfoldingButton.forEach(element => {

            if (element.classList.contains('unfolding-open')) {
                element.classList.add('active');
                if (element.hasAttribute('data-unfolding')) {
                    startUnfolding(element);

                } else {
                    activUnfolding(element.nextElementSibling);
                }
                element.classList.remove('unfolding-open');
            }

            element.addEventListener('click', function () {

                if (element.hasAttribute('data-unfolding')) {
                    startUnfolding(element);
                } else {
                    activUnfolding(this.nextElementSibling);
                }
            });
        });

        function startUnfolding(element) {

            let unfoldingObj = element.getAttribute('data-unfolding').split(',');
            let unfoldingClosest = element.closest('.' + unfoldingObj[1]);
            let unfoldingContent = unfoldingClosest.querySelector('.' + unfoldingObj[0]);

            if (unfoldingObj[1] == 'category-box') {
                activUnfoldingCategoryBox(element, unfoldingContent, unfoldingClosest)
            } else {
                activUnfolding(element, unfoldingContent);
            }
        }


        function activUnfoldingCategoryBox(element, body, unfoldingClosest) {


            if (body.style.maxHeight) {
                closeAllTabs();

            } else {
                closeAllTabs();
                body.style.maxHeight = body.scrollHeight + 'px';
                unfoldingClosest.style.marginBottom = body.scrollHeight + 'px';
                body.classList.add('active');
                element.classList.add('active');
            }


        }

        function closeAllTabs() {
            unfoldingButton.forEach(element => {
                if (element.hasAttribute('data-unfolding')) {

                    let unfoldingObj = element.getAttribute('data-unfolding').split(',');
                    let unfoldingClosest = element.closest('.' + unfoldingObj[1]);
                    let unfoldingContent = unfoldingClosest.querySelector('.' + unfoldingObj[0]);


                    if (unfoldingContent.style.maxHeight) {
                        unfoldingContent.style.maxHeight = null;
                        unfoldingClosest.style.marginBottom = null;
                        unfoldingContent.classList.remove('active');
                        element.classList.remove('active');
                    }

                }
            });
        }



        function activUnfolding(element, body) {
            if (body.style.maxHeight) {
                body.style.maxHeight = null;
            } else {
                body.style.maxHeight = body.scrollHeight + 'px';
            }
            body.classList.toggle('active');
            element.classList.toggle('active');
            // body.addEventListener('click', () => {
            //     setTimeout(function () {
            //         restartUnfolding(body);
            //     }, 200);
            // });

        }
        function restartUnfolding(body) {
            body.style.maxHeight = body.scrollHeight + 'px';
        }
    }



    //ПОПАП ОКНА  =============================================================================================================

    const popupLinks = document.querySelectorAll('.popup-link');
    const popups = document.querySelectorAll('.popup');
    const popupsCloses = document.querySelectorAll('.popup-close');

    if (popupLinks.length > 0) {
        popupLinks.forEach((item,) => {
            item.addEventListener('click', () => {
                console.log('2345');

                const popupName = item.getAttribute('data-popup');
                const curentPopup = document.getElementById(popupName);
                let itemLink = item;
                activPopup(curentPopup);
            })

        })
    }
    const cloasePopup = () => {
        popups.forEach((popup,) => {
            popup.classList.remove('active');
        });
        bodyUnfixPosition();
    }
    const activPopup = (item) => {
        popups.forEach((popup,) => {
            popup.classList.remove('active');
        });

        item.classList.toggle('active');
        bodyFixPosition();


        item.addEventListener('click', function (e) {
            if (!e.target.closest('.popup-body')) {
                popups.forEach((item,) => {
                    item.classList.remove('active');
                    bodyUnfixPosition();
                });


            }
        })

        popupsCloses.forEach((popupsClose,) => {
            popupsClose.addEventListener('click', function (e) {
                popups.forEach((item,) => {
                    item.classList.remove('active');
                    bodyUnfixPosition();
                })
            })
        });
    }

    //ПОПАП ОКНА  ------ ------------------------ end


    // ПЛАВНАЯ ПРОКРУТКА 

    // Пример для подключения:
    // <a href="#trigers" data-scroll="100,10,0"> Кнопка нажав на которую прокрутится страница </a>
    // trigers - id блока к которому пркручиваем страницу
    // 100 - скорость прокрутки
    // 10 - шаг прокрутки, в пикселях
    // 0 - отступ к блоку, в пикселях

    const scrollings = document.querySelectorAll('[data-scroll]');
    if (scrollings.length > 0) {
        let scrolled;
        let timer;

        let scrollPageYOffset;
        let curentScrollTop;
        let scrollingSpeed = 60;
        let scrollingTime = 10;
        let scrollingIndent = 0;


        scrollings.forEach((item,) => {
            item.addEventListener('click', (e) => {

                e.preventDefault();
                // bodyUnfixPosition();

                let scrollingObj = item.getAttribute('data-scroll').split(',');
                let scrollingName = item.getAttribute('href');
                scrollingName = scrollingName.replace("#", "");

                if (scrollingObj[0] != undefined && scrollingObj[0] != '') {
                    scrollingSpeed = Number(scrollingObj[0]);
                }
                if (scrollingObj[1] != undefined && scrollingObj[1] != '') {
                    scrollingTime = Number(scrollingObj[1]);
                }
                if (scrollingObj[2] != undefined && scrollingObj[2] != '') {
                    scrollingIndent = Number(scrollingObj[2]);
                }
                activScroll(scrollingName);
            });
        });

        const activScroll = (Name) => {
            const curentScroll = document.getElementById(Name);
            curentScrollTop = offset(curentScroll);
            curentScrollTop = curentScrollTop - scrollingIndent;

            scrollPageYOffset = window.pageYOffset;

            if (scrollPageYOffset < curentScrollTop) {
                scrollDown(curentScroll);
            } else {
                scrollToop(curentScroll);
            }
        }
        function scrollDown(curentScroll) {
            if (scrollPageYOffset < curentScrollTop) {

                scrollPageYOffset = scrollPageYOffset + scrollingSpeed; //100 - скорость прокрутки
                window.scrollTo(0, scrollPageYOffset);
                timer = setTimeout(scrollDown, scrollingTime);
            } else {
                clearTimeout(timer);

            }
        }
        function scrollToop(curentScroll) {
            if (scrollPageYOffset > curentScrollTop) {

                window.scrollTo(0, scrollPageYOffset);
                scrollPageYOffset = scrollPageYOffset - scrollingSpeed; //100 - скорость прокрутки
                timer = setTimeout(scrollToop, scrollingTime);
            } else {
                clearTimeout(timer);
            }
        }
        function offset(el) {
            const rect = el.getBoundingClientRect(),
                scrollTop = window.pageYOffset || document.documentElement.scrollTop;
            return (rect.top + scrollTop)
        }

    }


    // ПОДМЕНЮ =============================================================================================================

    let headerNavLinkAll = document.querySelectorAll('.li-sub-menu > a');

    if (headerNavLinkAll.length > 0) {
        headerNavLinkAll.forEach(headerNavLink => {
            headerNavLink.addEventListener('click', (e) => {
                e.preventDefault();
                // hideSubMenu();
                let nextElement = headerNavLink.nextElementSibling;
                activeSubMenu(headerNavLink, nextElement);
            })
            // headerNavLink.addEventListener('mouseover', function (event) {
            //     hideSubMenu();
            //     let nextElement = headerNavLink.nextElementSibling;
            //     activeSubMenu(headerNavLink, nextElement);
            // });
            // headerNavLink.addEventListener('mouseout', function (event) {
            //     hideSubMenu();
            // });

        });


        document.addEventListener('click', function (e) {
            if (!e.target.closest('.li-sub-menu > a')) {
                hideSubMenu();
            }
        });

        function activeSubMenu(headerNavLink, nextElement) {
            headerNavLink.classList.toggle('active');
            nextElement.classList.toggle('active');
        }

        function hideSubMenu() {
            headerNavLinkAll.forEach(headerNavLink => {
                let nextElement = headerNavLink.nextElementSibling;
                headerNavLink.classList.remove('active');
                nextElement.classList.remove('active');
            });

        }
    }





    // ЗАПРЕТ СКРОЛА =============================================================================================================

    // 1. Фиксация <body>
    function bodyFixPosition() {

        setTimeout(function () {
            if (!document.body.hasAttribute('data-body-scroll-fix')) {
                let scrollPosition = window.pageYOffset || document.documentElement.scrollTop;
                document.body.setAttribute('data-body-scroll-fix', scrollPosition);
                document.body.style.overflow = 'hidden';
                document.body.style.position = 'fixed';
                document.body.style.top = '-' + scrollPosition + 'px';
                document.body.style.left = '0';
                document.body.style.width = '100%';
            }
        }, 15);

    }
    // 2. Расфиксация <body>
    function bodyUnfixPosition() {

        if (document.body.hasAttribute('data-body-scroll-fix')) {
            let scrollPosition = document.body.getAttribute('data-body-scroll-fix');
            document.body.removeAttribute('data-body-scroll-fix');
            document.body.style.overflow = '';
            document.body.style.position = '';
            document.body.style.top = '';
            document.body.style.left = '';
            document.body.style.width = '';
            window.scroll(0, scrollPosition);
        }
    }






    // ВАЛИДАЦИЯ ФОРМЫ =============================================================================================================

    const feedbackForms = document.querySelectorAll('.form-validation form');

    // const textEmptyField = document.getElementById('start_form_empty').value;
    // const textNoFormat = document.getElementById('start_form_invalid').value;
    // const textPolicy = document.getElementById('start_form_polity').value;
    // const thankPage = document.getElementById('start_form_thank_link').value;


    const textEmptyField = 'Заполните обязательные поля!'
    const textNoFormat = 'Ввод содержит недопустимые символы.'
    const textPolicy = 'Важно согласиться с условиями'
    const thankPage = '/spasibo/'

    if (feedbackForms.length > 0) {
        feedbackForms.forEach(form => {
            let formBnt = form.querySelector(`[type="submit"]`);
            formBnt.addEventListener('click', (e) => {
                mainformSend(e, form);
            });
        });
    }
    async function mainformSend(e, form) {


        let result = mainformValidate(form);
        let error = result[0];
        let invalid = result[1];

        if (error === 404) {
            e.preventDefault();
        } else {
            if (error === 0) {
                if (invalid === 0) {
                    alert('Все буде добре!');
                } else {
                    alert(textNoFormat);
                    e.preventDefault();
                }
            } else {
                alert(textEmptyField);
                e.preventDefault();
            }
        }


    }


    function mainformValidate(form) {

        let error = 0;
        let invalid = 0;

        let formInputsAll = form.querySelectorAll('input');
        let formReq = form.querySelectorAll('._req');
        let formInvalidAll = form.querySelectorAll('._invalid');
        let inputNameAll = form.querySelectorAll('._name');


        formInputsAll.forEach(formInput => {
            mainformRemoveError(formInput);
        });



        for (var i = formReq.length - 1; i >= 0; i--) {
            let input = formReq[i];

            if (input.classList.contains("_policy")) {
                if (!input.checked) {
                    mainformAddError(input);
                    alert(textPolicy);
                    return [404, ''];
                }
            }

            if (input.classList.contains("_tel-plus")) {
                let patternPhone = new RegExp(`^\\+?${countryData.dialCode}-\\d{3}-\\d{3}-\\d{3}$`);
                let result = patternPhone.test(input.value);

                if (!result) {
                    mainformAddError(input);
                    error++
                }
            }

            if (input.getAttribute("type") === 'checkbox') {
                if (!input.checked) {
                    mainformAddError(input);
                    error++
                }
            }
            if (input.value === '') {
                mainformAddError(input);
                error++
            }
        }

        if (formInvalidAll.length > 0) {
            formInvalidAll.forEach(formInvalid => {
                if (regexText(formInvalid.value)) {
                    mainformAddError(formInvalid);
                    invalid++;
                }
            });
        }

        if (inputNameAll.length > 0) {
            inputNameAll.forEach(inputName => {
                if (regexName(inputName.value)) {
                    mainformAddError(inputName);
                    invalid++;
                } else {
                }
            });
        }

        return [error, invalid];
    }
    function mainformAddError(input) {
        input.parentElement.classList.add('error');
        input.classList.add('error');
    }
    function mainformRemoveError(input) {
        input.parentElement.classList.remove('error');
        input.classList.remove('error');
    }

    function regexText(str) {
        // Регулярное выражение, разрешающее только буквы , цифры
        var regex = /^[а-яА-ЯёЁa-zA-Z0-9]+$/;
        return !regex.test(str);
    }

    function regexName(str) {
        // Регулярное выражение, для ввода имени
        var regex = /^[а-яА-ЯёЁa-zA-Z]+$/;
        return !regex.test(str);
    }



    // async function mainformSend(e, form, url) {
    //     e.preventDefault();
    //     let error = mainformValidate(form);
    //     let formData = new FormData(form);
    //     if (error === 0) {
    //         sendingMain.classList.add('active');
    //         let response = await fetch(url, {
    //             method: 'POST',
    //             body: formData
    //         });
    //         if (response.ok) {
    //             let result = await response.json();

    //             if (result.err) {
    //                 alert(result.err);
    //             } else if (result.okSend) {
    //                 window.location.href = 'thank.html';
    //                 // alert(result.okSend);
    //             } else {
    //                 alert('Необработанная ошибка. Проверьте консоль и устраните.');
    //             }

    //             form.reset();
    //             sendingMain.classList.remove('active');

    //         } else {
    //             alert('Произошла ошибка, попробуйте позже!');
    //             sendingMain.classList.remove('active');
    //         };
    //     } else {
    //         alert('Заполните обязательные поля!');
    //     }
    // }


    // let wpcf7Elm = document.querySelector('.wpcf7');
    // if (wpcf7Elm) {
    //     let popupNoSend = document.getElementById('popup-no-send');
    //     let popupOk = document.getElementById('popup-ok');

    //     wpcf7Elm.addEventListener('wpcf7mailsent', function () {
    //         if (popupOk) {
    //             activPopup(popupOk);
    //         }
    //     });
    //     wpcf7Elm.addEventListener('wpcf7spam', function () {
    //         if (popupNoSend) {
    //             activPopup(popupNoSend);
    //         }
    //     });
    //     wpcf7Elm.addEventListener('wpcf7invalid', function () {
    //         if (popupNoSend) {
    //             activPopup(popupNoSend);
    //         }
    //     });

    //     wpcf7Elm.addEventListener('wpcf7mailfailed', function () {
    //         if (popupNoSend) {
    //             activPopup(popupNoSend);
    //         }
    //     });
    // }

    //--------------------------------------------- end


}


