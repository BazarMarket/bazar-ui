// АНИМАЦИЯ ПРИ СКРОЛЛЕ

// data-animate="animate__animated,animate__fast" - общие классы настройки из библиотеки Animate.css, передавать обязательно через зяпятую


// data-animate-desktop="animate__fadeInLeft,2000" - больше 993
// data-animate-table="animate__fadeInLeft,2000" - от 576 до 993
// data-animate-mob="animate__fadeInUp,3000" - меньше 576

// Настройки для адаптации, первым параметром передаётся класс выхода элемента, а вторым задержка проявления анимации в миллисекундах, передавать обязательно через запятую 


const animateArray = document.querySelectorAll('[data-animate]');
const screenWidth = window.innerWidth || document.documentElement.clientWidth || document.body.clientWidth;


if (animateArray.length > 0) {
   window.addEventListener('scroll', animOnScroll);


   function animOnScroll() {
      for (let index = 0; index < animateArray.length; index++) {
         const animateItem = animateArray[index];
         const animateItemHeigth = animateItem.offsetHeight;
         const animateItemTop = offset(animateItem);
         const animateStart = 4;

         if (!animateItem.classList.contains('animate__animated')) {
            animateItem.style.opacity = 0;
            animateItem.style.visibility = 'hidden';
         }

         let animatePoint = window.innerHeight - animateItemHeigth / animateStart;
         if (animateItemHeigth > window.innerHeight) {
            animatePoint = window.innerHeight - window.innerHeight / animateStart;
         }


         if ((window.scrollY > animateItemTop - animatePoint) && window.scrollY < (animateItemTop + animateItemHeigth)) {

            const animateItemClass = animateItem.getAttribute('data-animate').split(',');



            if (animateItem.hasAttribute('data-animate-desktop') || animateItem.hasAttribute('data-animate-table') || animateItem.hasAttribute('data-animate-mob')) {

               let animateItemDelay = 0;
               let animateItemClassIn;
               let animateItemClassPlus;



               if (animateItem.hasAttribute('data-animate-desktop')) {
                  animateItemClassPlus = animateItem.getAttribute('data-animate-desktop').split(',');
                  animateItemClassIn = animateItemClassPlus[0];
                  animateItemDelay = animateItemClassPlus[1];
               }

               if (screenWidth < 993) {
                  if (animateItem.hasAttribute('data-animate-table')) {
                     animateItemClassPlus = animateItem.getAttribute('data-animate-table').split(',');
                     animateItemClassIn = animateItemClassPlus[0];
                     animateItemDelay = animateItemClassPlus[1];
                  }
               }

               if (screenWidth < 576) {
                  if (animateItem.hasAttribute('data-animate-mob')) {
                     animateItemClassPlus = animateItem.getAttribute('data-animate-mob').split(',');
                     animateItemClassIn = animateItemClassPlus[0];
                     animateItemDelay = animateItemClassPlus[1];
                  }
               }

               animateItemDelay = Number(animateItemDelay);

               setTimeout(function () {
                  animateItem.classList.add(animateItemClassIn);
                  addAnimation(animateItem, animateItemClass)
               }, animateItemDelay);

            } else {
               addAnimation(animateItem, animateItemClass)
            }

         } else {
            // for (let index = 0; index < animateItemClass.length; index++) {
            //    const animateItemClassItem = animateItemClass[index];
            //    animateItem.classList.remove(animateItemClassItem);
            // }
            // animateItem.style.opacity = 0;
            // animateItem.style.visibility = 'hidden';

         }

      }
   }
   function offset(el) {
      const rect = el.getBoundingClientRect(),
         scrollTop = window.scrollY || document.documentElement.scrollTop;
      return (rect.top + scrollTop)
   }

   function addAnimation(animateItem, animateItemClass) {
      animateItemClass.forEach(element => {
         animateItem.classList.add(element);
      });

      animateItem.style.opacity = 1;
      animateItem.style.visibility = 'visible';
   }
   animOnScroll();


}