var LocationAutocomplete = {
  service: null,
  geocoder: null,
  debounceTimer: null,

  init: function(inputId, dropdownId) {
    var self = this;
    var input = document.getElementById(inputId);
    if (!input) return;

    if (!this.service && window.google && google.maps && google.maps.places) {
      this.service = new google.maps.places.AutocompleteService();
      this.geocoder = new google.maps.Geocoder();
    }

    input.addEventListener('input', function() {
      clearTimeout(self.debounceTimer);
      var query = input.value.trim();
      if (query.length < 2) return;

      self.debounceTimer = setTimeout(function() {
        self.fetchSuggestions(query, inputId, dropdownId);
      }, 250);
    });
  },

  fetchSuggestions: function(query, inputId, dropdownId) {
    var self = this;
    if (!this.service) {
      if (window.google && google.maps && google.maps.places) {
        this.service = new google.maps.places.AutocompleteService();
        this.geocoder = new google.maps.Geocoder();
      } else return;
    }

    this.service.getPlacePredictions({
      input: query,
      types: ['(regions)'],
      componentRestrictions: { country: 'gb' }
    }, function(predictions, status) {
      if (status !== google.maps.places.PlacesServiceStatus.OK || !predictions) return;
      self.showResults(predictions, inputId, dropdownId);
    });
  },

  showResults: function(predictions, inputId, dropdownId) {
    var self = this;
    var dd = document.getElementById(dropdownId);
    if (!dd) return;

    var items = dd.querySelectorAll('.loc-dropdown__item--result');
    for (var i = items.length - 1; i >= 0; i--) {
      items[i].parentNode.removeChild(items[i]);
    }

    predictions.forEach(function(p) {
      var mainText = p.structured_formatting ? p.structured_formatting.main_text : p.description;
      var secondaryText = p.structured_formatting ? p.structured_formatting.secondary_text : '';
      var div = document.createElement('div');
      div.className = 'loc-dropdown__item loc-dropdown__item--result';
      div.innerHTML = '<svg class="loc-dropdown__pin" width="14" height="14" viewBox="0 0 16 16" fill="none"><path d="M8 1C5.2 1 3 3.1 3 5.7 3 9.5 8 15 8 15s5-5.5 5-9.3C13 3.1 10.8 1 8 1z" stroke="#888" stroke-width="1.3"/><circle cx="8" cy="5.7" r="1.5" fill="#888"/></svg>' +
        '<span>' + mainText + (secondaryText ? ' <span style="color:#999;font-weight:400;font-size:12px">' + secondaryText + '</span>' : '') + '</span>';
      div.addEventListener('click', function() {
        self.selectPlace(p, inputId, dropdownId);
      });
      dd.appendChild(div);
    });

    dd.classList.add('open');
  },

  selectPlace: function(prediction, inputId, dropdownId) {
    var input = document.getElementById(inputId);
    var dd = document.getElementById(dropdownId);
    var mainText = prediction.structured_formatting ? prediction.structured_formatting.main_text : prediction.description;

    input.value = mainText;
    input.dataset.city = mainText;
    dd.classList.remove('open');

    var items = dd.querySelectorAll('.loc-dropdown__item--result');
    for (var i = items.length - 1; i >= 0; i--) {
      items[i].parentNode.removeChild(items[i]);
    }

    if (this.geocoder) {
      this.geocoder.geocode({ placeId: prediction.place_id }, function(results, status) {
        if (status === 'OK' && results[0] && results[0].geometry) {
          input.dataset.lat = results[0].geometry.location.lat();
          input.dataset.lng = results[0].geometry.location.lng();
        }
      });
    }
  },

  clearResults: function(dropdownId) {
    var dd = document.getElementById(dropdownId);
    if (!dd) return;
    var items = dd.querySelectorAll('.loc-dropdown__item--result');
    for (var i = items.length - 1; i >= 0; i--) {
      items[i].parentNode.removeChild(items[i]);
    }
  }
};
