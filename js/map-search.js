var MS = {
  map: null,
  markers: [],
  infoWindow: null,
  circle: null,
  activeId: null,
  radiusKm: 0,
  centerLat: 51.509,
  centerLng: -0.118,
  searchAreaBtn: null,
  pendingBounds: false,
  mobileView: 'list',

  LISTINGS: [
    {id:10,title:"2 Bedroom Apartment for Sale",price:425000,currency:"£",period:"",lat:51.5054,lng:-0.0235,city:"London",area:"Canary Wharf",img:"https://admin.bazar.uk/storage/properties/2f9028f8-3380-4cf4-9c35-bc80d844fbb3.jpg",beds:2,baths:1,sqm:185,type:"Apartment",vip:true,pro:false},
    {id:11,title:"4 Bedroom Detached House",price:375000,currency:"£",period:"",lat:53.4145,lng:-2.2214,city:"Manchester",area:"Didsbury",img:"https://admin.bazar.uk/storage/properties/81d6346f-f100-4873-91f7-37215b9777d0.jpg",beds:4,baths:2,sqm:180,type:"House",vip:true,pro:true},
    {id:12,title:"3 Bedroom Victorian Townhouse",price:295000,currency:"£",period:"",lat:51.4570,lng:-2.6167,city:"Bristol",area:"Clifton",img:"https://admin.bazar.uk/storage/properties/6355a3da-7157-475a-b890-dd8258f40367.jpg",beds:3,baths:2,sqm:140,type:"House",vip:false,pro:false},
    {id:13,title:"5 Bedroom Luxury Villa with Pool",price:1250000,currency:"£",period:"",lat:51.4002,lng:-0.5685,city:"Guildford",area:"Virginia Water",img:"https://admin.bazar.uk/storage/properties/93b9efe3-8d6d-4088-880e-814bbd2b20fe.jpg",beds:5,baths:3,sqm:320,type:"House",vip:true,pro:true},
    {id:14,title:"Studio Apartment, City Centre",price:125000,currency:"£",period:"",lat:53.8008,lng:-1.5491,city:"Leeds",area:"City Centre",img:"https://admin.bazar.uk/storage/properties/226abc8a-0deb-4b91-9848-4f9ef4b729e9.jpg",beds:0,baths:1,sqm:42,type:"Studio",vip:false,pro:false},
    {id:15,title:"2 Bedroom Maisonette",price:210000,currency:"£",period:"",lat:52.4741,lng:-1.9231,city:"Birmingham",area:"Edgbaston",img:"https://admin.bazar.uk/storage/properties/df6deedc-92b8-4469-9973-8e03e0226406.jpg",beds:2,baths:1,sqm:95,type:"Apartment",vip:false,pro:true},
    {id:16,title:"3 Bedroom Stone Cottage",price:485000,currency:"£",period:"",lat:51.8853,lng:-1.7591,city:"Bourton-on-the-Water",area:"Cotswolds",img:"https://admin.bazar.uk/storage/properties/f97e0894-ab60-4ee0-98e9-4a20e92ed1f4.jpg",beds:3,baths:2,sqm:150,type:"House",vip:true,pro:false},
    {id:17,title:"3 Bedroom Penthouse with City Views",price:550000,currency:"£",period:"",lat:53.4010,lng:-2.9946,city:"Liverpool",area:"Waterfront",img:"https://admin.bazar.uk/storage/properties/cf55b302-efe5-405c-bc3b-34a056780c6f.jpg",beds:3,baths:2,sqm:200,type:"Apartment",vip:false,pro:false},
    {id:40,title:"3 Bedroom House for Sale",price:1000000,currency:"£",period:"",lat:51.5389,lng:-0.2464,city:"London",area:"Harlesden",img:"https://admin.bazar.uk/storage/properties/82c4ef14-7f88-4bb0-80bf-3b782758aa6b.jpg",beds:3,baths:1,sqm:120,type:"House",vip:false,pro:false}
  ],

  formatPrice: function(p) {
    if (p >= 1000000) return '£' + (p/1000000).toFixed(1) + 'M';
    if (p >= 1000) return '£' + (p/1000).toFixed(p%1000===0?0:1) + 'k';
    return '£' + p;
  },

  formatPriceFull: function(l) {
    var s = l.currency + l.price.toLocaleString('en-GB');
    if (l.period) s += ' ' + l.period;
    return s;
  },

  init: function() {
    this.searchAreaBtn = document.getElementById('msSearchArea');
    this.renderList(this.LISTINGS);
    this.loadMap();
    this.bindEvents();
  },

  loadMap: function() {
    var self = this;
    fetch('/api/config').then(function(r){return r.json()}).then(function(cfg){
      if (window.google && window.google.maps) { self.initMap(); return; }
      window.msInitMap = function() { self.initMap(); };
      var s = document.createElement('script');
      s.src = 'https://maps.googleapis.com/maps/api/js?key=' + cfg.googleMapsApiKey + '&libraries=places&loading=async&callback=msInitMap';
      s.async = true; s.defer = true;
      document.head.appendChild(s);
    });
  },

  PriceOverlay: null,

  createOverlayClass: function() {
    var self = this;
    this.PriceOverlay = function(pos, listing, map) {
      this.pos = pos;
      this.listing = listing;
      this.div = null;
      this.setMap(map);
    };
    this.PriceOverlay.prototype = new google.maps.OverlayView();
    this.PriceOverlay.prototype.onAdd = function() {
      var div = document.createElement('div');
      var pinClass = 'ms-pin';
      if (this.listing.vip) pinClass += ' ms-pin--vip';
      else if (this.listing.pro) pinClass += ' ms-pin--pro';
      div.className = pinClass;
      div.textContent = self.formatPrice(this.listing.price);
      div.dataset.id = this.listing.id;
      this.div = div;
      var listing = this.listing;
      var overlay = this;
      div.addEventListener('click', function(e) {
        e.stopPropagation();
        self.selectListing(listing.id);
        self.showInfoWindow(listing, overlay);
      });
      div.addEventListener('mouseenter', function() {
        if (self.activeId !== listing.id) div.classList.add('hover');
      });
      div.addEventListener('mouseleave', function() {
        div.classList.remove('hover');
      });
      var panes = this.getPanes();
      panes.overlayMouseTarget.appendChild(div);
    };
    this.PriceOverlay.prototype.draw = function() {
      var proj = this.getProjection();
      var pt = proj.fromLatLngToDivPixel(this.pos);
      if (this.div) {
        this.div.style.position = 'absolute';
        this.div.style.left = pt.x + 'px';
        this.div.style.top = pt.y + 'px';
        this.div.style.transform = 'translate(-50%, -100%)';
      }
    };
    this.PriceOverlay.prototype.onRemove = function() {
      if (this.div && this.div.parentNode) this.div.parentNode.removeChild(this.div);
      this.div = null;
    };
    this.PriceOverlay.prototype.getPosition = function() { return this.pos; };
  },

  initMap: function() {
    var self = this;
    this.map = new google.maps.Map(document.getElementById('msMap'), {
      center: {lat: this.centerLat, lng: this.centerLng},
      zoom: 12,
      disableDefaultUI: true,
      zoomControl: true,
      gestureHandling: 'greedy',
      styles: [
        {featureType:"poi",stylers:[{visibility:"off"}]},
        {featureType:"transit",stylers:[{visibility:"off"}]},
        {featureType:"road",elementType:"labels.icon",stylers:[{visibility:"off"}]},
        {featureType:"water",elementType:"geometry",stylers:[{color:"#e9eff5"}]},
        {featureType:"landscape",elementType:"geometry",stylers:[{color:"#f5f5f5"}]}
      ]
    });

    this.createOverlayClass();
    this.infoWindow = new google.maps.InfoWindow({maxWidth: 300});

    this.addMarkers(this.LISTINGS);

    var firstIdle = true;
    this.map.addListener('idle', function() {
      if (firstIdle) { firstIdle = false; return; }
      self.searchAreaBtn.classList.add('visible');
    });
  },

  addMarkers: function(listings) {
    var self = this;
    this.clearMarkers();
    listings.forEach(function(l) {
      if (!l.lat || !l.lng) return;
      var overlay = new self.PriceOverlay(
        new google.maps.LatLng(l.lat, l.lng), l, self.map
      );
      overlay.listingId = l.id;
      self.markers.push(overlay);
    });
  },

  clearMarkers: function() {
    this.markers.forEach(function(m) { m.setMap(null); });
    this.markers = [];
  },

  showInfoWindow: function(listing, overlay) {
    var html = '<div class="ms-info" onclick="window.location.href=\'card.html\'">' +
      '<img class="ms-info-img" src="' + listing.img + '" alt="">' +
      '<div class="ms-info-body">' +
      '<div class="ms-info-price">' + this.formatPriceFull(listing) + '</div>' +
      '<div class="ms-info-title">' + listing.title + '</div>' +
      '<div class="ms-info-loc"><svg width="12" height="12" viewBox="0 0 16 16" fill="none"><path d="M8 1C5.2 1 3 3.1 3 5.7 3 9.5 8 15 8 15s5-5.5 5-9.3C13 3.1 10.8 1 8 1z" stroke="#999" stroke-width="1.2"/><circle cx="8" cy="5.7" r="1.3" fill="#999"/></svg>' + listing.area + ', ' + listing.city + '</div>' +
      '</div></div>';
    this.infoWindow.setContent(html);
    this.infoWindow.setPosition(overlay.pos || overlay.getPosition());
    this.infoWindow.open(this.map);
  },

  selectListing: function(id) {
    var prev = this.activeId;
    this.activeId = id;

    document.querySelectorAll('.ms-card').forEach(function(c) {
      c.classList.toggle('active', c.dataset.id == id);
    });

    this.markers.forEach(function(m) {
      var pin = m.content;
      if (pin) {
        pin.classList.toggle('active', m.listingId == id);
        if (m.listingId == id) {
          m.zIndex = 100;
        } else {
          m.zIndex = 1;
        }
      }
    });

    var card = document.querySelector('.ms-card[data-id="' + id + '"]');
    if (card) {
      card.scrollIntoView({behavior: 'smooth', block: 'nearest'});
    }
  },

  highlightPin: function(id, on) {
    this.markers.forEach(function(m) {
      if (m.listingId == id && m.content) {
        m.content.classList.toggle('hover', on);
      }
    });
  },

  renderList: function(listings) {
    var self = this;
    var container = document.getElementById('msListCards');
    var countEl = document.getElementById('msListCount');
    countEl.textContent = listings.length + ' properties';

    if (listings.length === 0) {
      container.innerHTML = '<div class="ms-empty"><div class="ms-empty-icon">📍</div><div class="ms-empty-title">No properties in this area</div><div class="ms-empty-text">Try zooming out or moving the map</div></div>';
      return;
    }

    container.innerHTML = listings.map(function(l) {
      var badges = '';
      if (l.vip) badges += '<span class="ms-card-badge ms-card-badge--vip">VIP</span>';
      if (l.pro) badges += '<span class="ms-card-badge ms-card-badge--pro">PRO</span>';

      return '<div class="ms-card" data-id="' + l.id + '">' +
        '<div class="ms-card-img"><img src="' + l.img + '" alt="" loading="lazy"></div>' +
        '<div class="ms-card-body">' +
        (badges ? '<div class="ms-card-badges">' + badges + '</div>' : '') +
        '<div class="ms-card-title">' + l.title + '</div>' +
        '<div class="ms-card-location"><svg width="12" height="12" viewBox="0 0 16 16" fill="none"><path d="M8 1C5.2 1 3 3.1 3 5.7 3 9.5 8 15 8 15s5-5.5 5-9.3C13 3.1 10.8 1 8 1z" stroke="#999" stroke-width="1.2"/><circle cx="8" cy="5.7" r="1.3" fill="#999"/></svg>' + l.area + ', ' + l.city + '</div>' +
        '<div class="ms-card-meta">' +
        (l.beds > 0 ? '<span>🛏 ' + l.beds + '</span>' : '') +
        '<span>🚿 ' + l.baths + '</span>' +
        '<span>📐 ' + l.sqm + ' m²</span>' +
        '</div>' +
        '<div class="ms-card-price">' + self.formatPriceFull(l) + '</div>' +
        '</div></div>';
    }).join('');

    container.querySelectorAll('.ms-card').forEach(function(card) {
      card.addEventListener('click', function() {
        var id = parseInt(this.dataset.id);
        self.selectListing(id);
        var listing = self.LISTINGS.find(function(l){return l.id===id});
        if (listing && self.map) {
          self.map.panTo({lat: listing.lat, lng: listing.lng});
          var marker = self.markers.find(function(m){return m.listingId===id});
          if (marker) self.showInfoWindow(listing, marker);
        }
      });
      card.addEventListener('mouseenter', function() {
        self.highlightPin(parseInt(this.dataset.id), true);
      });
      card.addEventListener('mouseleave', function() {
        self.highlightPin(parseInt(this.dataset.id), false);
      });
    });
  },

  searchThisArea: function() {
    if (!this.map) return;
    var bounds = this.map.getBounds();
    var self = this;
    var visible = this.LISTINGS.filter(function(l) {
      if (!l.lat || !l.lng) return false;
      return bounds.contains({lat: l.lat, lng: l.lng});
    });

    if (this.radiusKm > 0 && this.circle) {
      var center = this.circle.getCenter();
      visible = visible.filter(function(l) {
        var d = google.maps.geometry ? google.maps.geometry.spherical.computeDistanceBetween(
          new google.maps.LatLng(l.lat, l.lng), center
        ) : self.haversine(l.lat, l.lng, center.lat(), center.lng());
        return d <= self.radiusKm * 1000;
      });
    }

    this.renderList(visible);
    this.clearMarkers();
    this.addMarkers(visible);
    this.searchAreaBtn.classList.remove('visible');
    this.pendingBounds = false;
  },

  haversine: function(lat1, lng1, lat2, lng2) {
    var R = 6371000;
    var dLat = (lat2 - lat1) * Math.PI / 180;
    var dLng = (lng2 - lng1) * Math.PI / 180;
    var a = Math.sin(dLat/2)*Math.sin(dLat/2) +
            Math.cos(lat1*Math.PI/180)*Math.cos(lat2*Math.PI/180)*
            Math.sin(dLng/2)*Math.sin(dLng/2);
    return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
  },

  setRadius: function(km, btn) {
    document.querySelectorAll('.ms-radius-chip').forEach(function(c){c.classList.remove('active')});
    if (this.radiusKm === km) {
      this.radiusKm = 0;
      if (this.circle) { this.circle.setMap(null); this.circle = null; }
      return;
    }
    this.radiusKm = km;
    btn.classList.add('active');

    var center = this.map ? this.map.getCenter() : {lat:function(){return MS.centerLat},lng:function(){return MS.centerLng}};

    if (this.circle) this.circle.setMap(null);
    this.circle = new google.maps.Circle({
      map: this.map,
      center: {lat: center.lat(), lng: center.lng()},
      radius: km * 1000,
      fillColor: '#ff9138',
      fillOpacity: 0.08,
      strokeColor: '#ff9138',
      strokeWeight: 1.5,
      strokeOpacity: 0.4,
      clickable: false
    });

    var b = this.circle.getBounds();
    if (b && this.map) this.map.fitBounds(b);

    this.searchAreaBtn.classList.add('visible');
  },

  toggleMobileView: function() {
    var listPanel = document.querySelector('.ms-list-panel');
    var mapPanel = document.querySelector('.ms-map-panel');
    var toggleBtn = document.getElementById('msMobileToggle');

    if (this.mobileView === 'list') {
      this.mobileView = 'map';
      listPanel.classList.add('hidden');
      mapPanel.classList.add('visible');
      mapPanel.classList.remove('hidden');
      toggleBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg> Show list';
      if (this.map) google.maps.event.trigger(this.map, 'resize');
    } else {
      this.mobileView = 'list';
      listPanel.classList.remove('hidden');
      mapPanel.classList.remove('visible');
      toggleBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="12" cy="10" r="3"/><path d="M12 13v4"/></svg> Show map';
    }
  },

  bindEvents: function() {
    var self = this;
    this.searchAreaBtn.addEventListener('click', function() {
      self.searchThisArea();
    });
    document.getElementById('msMobileToggle').addEventListener('click', function() {
      self.toggleMobileView();
    });
  }
};

window.MS = MS;

document.addEventListener('DOMContentLoaded', function() {
  MS.init();
});
