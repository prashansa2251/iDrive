// Water Bodies Map Application
// Implements features for managing water bodies with custom attributes

class WaterBodiesMap {
    constructor() {
        this.map = null;
        this.waterbodies = [];
        this.currentEditingLayer = null;
        this.drawnItems = new L.FeatureGroup();
        this.init();
    }

    init() {
        this.initMap();
        this.initDrawControl();
        this.bindEvents();
        this.loadWaterbodies();
    }

    initMap() {
        // Initialize Leaflet map
        this.map = L.map('map').setView([39.8283, -98.5795], 4); // Center on US

        // Add OpenStreetMap tiles
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        }).addTo(this.map);

        // Add drawn items to map
        this.map.addLayer(this.drawnItems);
    }

    initDrawControl() {
        // Initialize Leaflet.draw controls
        const drawControl = new L.Control.Draw({
            edit: {
                featureGroup: this.drawnItems,
                remove: true
            },
            draw: {
                rectangle: false,
                circle: false,
                circlemarker: false,
                marker: false,
                polyline: false,
                polygon: {
                    allowIntersection: false,
                    drawError: {
                        color: '#e1e100',
                        message: '<strong>Error:</strong> shape edges cannot cross!'
                    },
                    shapeOptions: {
                        color: '#0078ff'
                    }
                }
            }
        });

        this.map.addControl(drawControl);
    }

    bindEvents() {
        // Bind form submission
        document.getElementById('waterbodyForm').addEventListener('submit', (e) => {
            e.preventDefault();
            this.addWaterbody();
        });

        // Bind map drawing events
        this.map.on(L.Draw.Event.CREATED, (e) => {
            const layer = e.layer;
            this.drawnItems.addLayer(layer);
            this.showWaterbodyForm(layer);
        });

        // Bind edit events for auto-focus feature
        this.map.on(L.Draw.Event.EDITED, (e) => {
            e.layers.eachLayer((layer) => {
                this.focusOnWaterbody(layer);
            });
        });

        // Bind delete events for auto-focus feature
        this.map.on(L.Draw.Event.DELETED, (e) => {
            e.layers.eachLayer((layer) => {
                // Focus on the center of the deleted area before it's removed
                this.focusOnWaterbody(layer);
                // Remove from waterbodies array
                this.waterbodies = this.waterbodies.filter(wb => wb.layer !== layer);
                // Update statistics after deletion
                this.updateStatistics();
            });
        });

        // Close form button
        document.getElementById('closeFormBtn').addEventListener('click', () => {
            this.hideWaterbodyForm();
        });

        // Cancel form button
        document.getElementById('cancelFormBtn').addEventListener('click', () => {
            this.hideWaterbodyForm();
            // Remove the temporary layer if form is cancelled
            if (this.currentEditingLayer) {
                this.drawnItems.removeLayer(this.currentEditingLayer);
                this.currentEditingLayer = null;
            }
        });
    }

    showWaterbodyForm(layer = null) {
        this.currentEditingLayer = layer;
        const form = document.getElementById('waterbodyFormContainer');
        form.classList.remove('d-none');
        
        // Reset form
        document.getElementById('waterbodyForm').reset();
        
        // Focus on first input
        document.getElementById('waterbodyId').focus();
    }

    hideWaterbodyForm() {
        const form = document.getElementById('waterbodyFormContainer');
        form.classList.add('d-none');
        this.currentEditingLayer = null;
    }

    addWaterbody() {
        const formData = new FormData(document.getElementById('waterbodyForm'));
        const waterbodyData = {
            id: formData.get('waterbodyId'),
            type: formData.get('type'),
            maxDepth: parseFloat(formData.get('maxDepth')),
            spreadArea: parseFloat(formData.get('spreadArea')),
            shapeArea: parseFloat(formData.get('shapeArea')),
            minYield: parseFloat(formData.get('minYield')),
            maxYield: parseFloat(formData.get('maxYield')),
            storageCapacity: parseFloat(formData.get('storageCapacity')),
            layer: this.currentEditingLayer,
            coordinates: this.currentEditingLayer ? this.currentEditingLayer.getLatLngs() : null
        };

        // Validate required fields
        if (!waterbodyData.id || !waterbodyData.type) {
            alert('Please fill in all required fields (Water Body ID and Type)');
            return;
        }

        // Check for duplicate IDs
        if (this.waterbodies.some(wb => wb.id === waterbodyData.id)) {
            alert('Water Body ID already exists. Please use a unique ID.');
            return;
        }

        // Add popup to the layer
        if (this.currentEditingLayer) {
            const popupContent = this.createPopupContent(waterbodyData);
            this.currentEditingLayer.bindPopup(popupContent);
            
            // Style the layer
            this.currentEditingLayer.setStyle({
                fillColor: this.getTypeColor(waterbodyData.type),
                fillOpacity: 0.5,
                color: '#0078ff',
                weight: 2
            });
        }

        // Add to waterbodies array
        this.waterbodies.push(waterbodyData);

        // Focus on the new waterbody
        if (this.currentEditingLayer) {
            this.focusOnWaterbody(this.currentEditingLayer);
        }

        // Hide form
        this.hideWaterbodyForm();

        // Show success message
        this.showToast(`Water body "${waterbodyData.id}" added successfully!`);

        // Save to local storage (in a real app, this would be saved to database)
        this.saveWaterbodies();
        
        // Update statistics
        this.updateStatistics();
    }

    createPopupContent(waterbodyData) {
        return `
            <div class="waterbody-popup">
                <h6 class="mb-2"><strong>${waterbodyData.id}</strong></h6>
                <div class="popup-content">
                    <p><strong>Type:</strong> ${waterbodyData.type}</p>
                    <p><strong>Max Depth:</strong> ${waterbodyData.maxDepth || 'N/A'} m</p>
                    <p><strong>Spread Area:</strong> ${waterbodyData.spreadArea || 'N/A'} ha</p>
                    <p><strong>Shape Area:</strong> ${waterbodyData.shapeArea || 'N/A'} ha</p>
                    <p><strong>Min Yield:</strong> ${waterbodyData.minYield || 'N/A'} m³</p>
                    <p><strong>Max Yield:</strong> ${waterbodyData.maxYield || 'N/A'} m³</p>
                    <p><strong>Storage Capacity:</strong> ${waterbodyData.storageCapacity || 'N/A'} m³</p>
                </div>
            </div>
        `;
    }

    getTypeColor(type) {
        const colors = {
            'lake': '#4A90E2',
            'pond': '#50E3C2',
            'reservoir': '#F5A623',
            'river': '#7ED321',
            'stream': '#417505',
            'wetland': '#BD10E0',
            'other': '#B8E986'
        };
        return colors[type.toLowerCase()] || colors.other;
    }

    focusOnWaterbody(layer) {
        if (layer && layer.getBounds) {
            // Zoom to the waterbody with some padding
            this.map.fitBounds(layer.getBounds(), {
                padding: [20, 20],
                maxZoom: 15
            });
        } else if (layer && layer.getLatLng) {
            // For point features
            this.map.setView(layer.getLatLng(), 15);
        }
    }

    loadWaterbodies() {
        // Load waterbodies from local storage (in a real app, this would load from database)
        const saved = localStorage.getItem('waterbodies');
        if (saved) {
            try {
                const data = JSON.parse(saved);
                data.forEach(wb => {
                    if (wb.coordinates) {
                        // Recreate the layer from coordinates
                        const layer = L.polygon(wb.coordinates);
                        layer.setStyle({
                            fillColor: this.getTypeColor(wb.type),
                            fillOpacity: 0.5,
                            color: '#0078ff',
                            weight: 2
                        });
                        
                        // Add popup
                        const popupContent = this.createPopupContent(wb);
                        layer.bindPopup(popupContent);
                        
                        // Add to map
                        this.drawnItems.addLayer(layer);
                        
                        // Update waterbody data with new layer reference
                        wb.layer = layer;
                        this.waterbodies.push(wb);
                    }
                });
                
                // Update statistics after loading
                this.updateStatistics();
            } catch (e) {
                console.error('Error loading waterbodies:', e);
            }
        }
    }

    saveWaterbodies() {
        // Save waterbodies to local storage (in a real app, this would save to database)
        const dataToSave = this.waterbodies.map(wb => ({
            id: wb.id,
            type: wb.type,
            maxDepth: wb.maxDepth,
            spreadArea: wb.spreadArea,
            shapeArea: wb.shapeArea,
            minYield: wb.minYield,
            maxYield: wb.maxYield,
            storageCapacity: wb.storageCapacity,
            coordinates: wb.coordinates
        }));
        localStorage.setItem('waterbodies', JSON.stringify(dataToSave));
    }

    showToast(message) {
        // Show success toast using the existing toast system
        if (typeof showToast === 'function') {
            showToast(message);
        } else {
            alert(message);
        }
    }

    // Public method to focus on a specific waterbody by ID
    focusOnWaterbodyById(id) {
        const waterbody = this.waterbodies.find(wb => wb.id === id);
        if (waterbody && waterbody.layer) {
            this.focusOnWaterbody(waterbody.layer);
            waterbody.layer.openPopup();
        }
    }

    // Public method to get all waterbodies
    getWaterbodies() {
        return this.waterbodies;
    }

    // Update statistics display
    updateStatistics() {
        const countElement = document.getElementById('waterbodiesCount');
        if (countElement) {
            countElement.textContent = this.waterbodies.length;
        }
    }
}

// Initialize map when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Check if we're on the map page
    if (document.getElementById('map')) {
        window.waterBodiesMap = new WaterBodiesMap();
    }
});