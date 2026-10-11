
"use strict";

// ========================================
// 1. CONFIGURATION
// ========================================

const API_BASE_URL = "http://127.0.0.1:8000";
const HEALTH_ENDPOINT = `${API_BASE_URL}/health`;

// Demo data is for frontend testing only.
// These are fictional records, NOT real clinics.
const DEMO_CLINICS = [
    {
        id: "demo-001",
        name: "Demo Clinic A",
        specialty: "General Medicine",
        area: "New Town, Kolkata",
        distanceKm: 1.2,
        homeCollection: true,
        phone: null,
        isDemo: true
    },
    {
        id: "demo-002",
        name: "Demo Clinic B",
        specialty: "Dermatology",
        area: "Salt Lake, Kolkata",
        distanceKm: 3.4,
        homeCollection: false,
        phone: null,
        isDemo: true
    },
    {
        id: "demo-003",
        name: "Demo Clinic C",
        specialty: "General Medicine",
        area: "Rajarhat, Kolkata",
        distanceKm: 6.8,
        homeCollection: true,
        phone: null,
        isDemo: true
    }
];


// ========================================
// 2. DOM ELEMENTS
// ========================================

const searchForm = document.getElementById("clinic-search-form");
const locationInput = document.getElementById("location");
const queryInput = document.getElementById("search-query");
const radiusSelect = document.getElementById("radius");
const homeCollectionSelect = document.getElementById("home-collection");
const searchButton = document.getElementById("search-button");
const searchStatus = document.getElementById("search-status");
const resultsContainer = document.getElementById("clinic-results");


// ========================================
// 3. APPLICATION STATE
// ========================================

let isSearching = false;
let backendAvailable = false;


// ========================================
// 4. BACKEND HEALTH CHECK
// ========================================

async function checkBackendHealth() {
    try {
        const response = await fetch(HEALTH_ENDPOINT, {
            method: "GET",
            headers: {
                Accept: "application/json"
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();

        // The existing backend returns:
        // {"status": "ok", "service": "clinic-discovery-api"}
        if (data.status !== "ok") {
            throw new Error("Unexpected health response");
        }

        backendAvailable = true;

        console.info("Backend connection successful:", data);

        return true;
    } catch (error) {
        backendAvailable = false;

        console.warn("Backend health check failed:", error.message);

        return false;
    }
}


// ========================================
// 5. UI HELPERS
// ========================================

function setSearchStatus(message, type = "info") {
    searchStatus.textContent = message;
    searchStatus.dataset.type = type;
}

function setLoading(isLoading) {
    isSearching = isLoading;
    searchButton.disabled = isLoading;

    searchButton.textContent = isLoading
        ? "Searching..."
        : "Search clinics";

    resultsContainer.setAttribute(
        "aria-busy",
        String(isLoading)
    );
}

function clearResults() {
    resultsContainer.replaceChildren();
}

function showMessage(message, className = "empty-state") {
    clearResults();

    const paragraph = document.createElement("p");
    paragraph.className = className;
    paragraph.textContent = message;

    resultsContainer.appendChild(paragraph);
}


// ========================================
// 6. SAFE CLINIC CARD RENDERING
// ========================================

function createClinicCard(clinic) {
    const card = document.createElement("article");
    card.className = "clinic-card";

    const badge = document.createElement("p");
    badge.className = "demo-badge";
    badge.textContent = "DEMO DATA — NOT VERIFIED";

    const name = document.createElement("h3");
    name.textContent = clinic.name;

    const specialty = document.createElement("p");
    specialty.textContent = `Specialty: ${clinic.specialty}`;

    const area = document.createElement("p");
    area.textContent = `Area: ${clinic.area}`;

    const distance = document.createElement("p");
    distance.textContent = `Demo distance: ${clinic.distanceKm} km`;

    const collection = document.createElement("p");
    collection.textContent = clinic.homeCollection
        ? "Home sample collection: Demo availability only"
        : "Home sample collection: Not available in this demo record";

    const disclaimer = document.createElement("p");
    disclaimer.className = "clinic-disclaimer";
    disclaimer.textContent =
        "Fictional example. This is not a real clinic or verified service.";

    card.append(
        badge,
        name,
        specialty,
        area,
        distance,
        collection,
        disclaimer
    );

    return card;
}

function renderClinics(clinics) {
    clearResults();

    if (clinics.length === 0) {
        showMessage("No demo records match your selected filters.");
        return;
    }

    const fragment = document.createDocumentFragment();

    clinics.forEach((clinic) => {
        fragment.appendChild(createClinicCard(clinic));
    });

    resultsContainer.appendChild(fragment);
}


// ========================================
// 7. FORM VALIDATION AND INPUT
// ========================================

function getSearchCriteria() {
    const location = locationInput.value.trim();
    const query = queryInput.value.trim();
    const radiusKm = Number(radiusSelect.value);
    const homeCollection = homeCollectionSelect.value;

    if (!location || !query) {
        throw new Error("Please enter your location and healthcare need.");
    }

    if (
        !Number.isFinite(radiusKm) ||
        ![2, 5, 10, 20].includes(radiusKm)
    ) {
        throw new Error("Please select a valid search distance.");
    }

    if (!["any", "available", "unavailable"].includes(homeCollection)) {
        throw new Error("Please select a valid home collection filter.");
    }

    return {
        location,
        query,
        radiusKm,
        homeCollection
    };
}


// ========================================
// 8. DEMO SEARCH
// ========================================

function searchDemoClinics(criteria) {
    const normalizedQuery = criteria.query.toLowerCase();

    // Match the specialty against the requested service.
    // This is a simple demo filter, not medical interpretation.
    const queryFiltered = DEMO_CLINICS.filter((clinic) => {
        return (
            clinic.specialty.toLowerCase().includes(normalizedQuery) ||
            normalizedQuery.includes(clinic.specialty.toLowerCase())
        );
    });

    // For demo purposes, also allow a general medicine search.
    const relevantClinics = queryFiltered.length > 0
        ? queryFiltered
        : DEMO_CLINICS.filter((clinic) => {
            return clinic.specialty === "General Medicine" &&
                normalizedQuery.includes("general");
        });

    return relevantClinics.filter((clinic) => {
        const withinRadius = clinic.distanceKm <= criteria.radiusKm;

        const collectionMatches =
            criteria.homeCollection === "any" ||
            (
                criteria.homeCollection === "available" &&
                clinic.homeCollection
            ) ||
            (
                criteria.homeCollection === "unavailable" &&
                !clinic.homeCollection
            );

        return withinRadius && collectionMatches;
    });
}


// ========================================
// 9. HANDLE SEARCH SUBMISSION
// ========================================

async function handleSearch(event) {
    event.preventDefault();

    if (isSearching) {
        return;
    }

    let criteria;

    try {
        criteria = getSearchCriteria();
    } catch (error) {
        setSearchStatus(error.message, "error");
        showMessage("Please correct the search form and try again.");
        return;
    }

    setLoading(true);
    setSearchStatus("Checking backend connection...", "info");
    showMessage("Loading demo records...");

    try {
        const isBackendHealthy = await checkBackendHealth();

        if (!isBackendHealthy) {
            setSearchStatus(
                "Cannot reach the backend. Start FastAPI and try again.",
                "error"
            );

            showMessage(
                "Search is unavailable because the backend health check failed."
            );

            return;
        }

        setSearchStatus(
            "Backend connected. Showing fictional demo records only.",
            "success"
        );

        // IMPORTANT:
        // No real clinic-search API exists yet.
        // This function filters local fictional records only.
        const clinics = searchDemoClinics(criteria);

        renderClinics(clinics);

        if (clinics.length > 0) {
            setSearchStatus(
                `Showing ${clinics.length} fictional demo record(s). No real clinics were searched.`,
                "success"
            );
        } else {
            setSearchStatus(
                "No demo records match these filters. Real clinic search is not implemented.",
                "info"
            );
        }
    } catch (error) {
        console.error("Search failed:", error);

        setSearchStatus(
            "An unexpected error occurred. Please try again.",
            "error"
        );

        showMessage("Unable to complete the demo search.");
    } finally {
        setLoading(false);
    }
}


// ========================================
// 10. INITIALIZE FRONTEND
// ========================================

async function initializeApp() {
    if (
        !searchForm ||
        !locationInput ||
        !queryInput ||
        !radiusSelect ||
        !homeCollectionSelect ||
        !searchButton ||
        !searchStatus ||
        !resultsContainer
    ) {
        console.error(
            "Required HTML elements are missing. Check the element IDs."
        );
        return;
    }

    searchForm.addEventListener("submit", handleSearch);

    setSearchStatus("Checking backend connection...", "info");

    const isBackendHealthy = await checkBackendHealth();

    if (isBackendHealthy) {
        setSearchStatus("Backend connected successfully.", "success");
    } else {
        setSearchStatus(
            "Backend is not reachable. Start FastAPI to enable the demo search.",
            "error"
        );
    }
}

document.addEventListener("DOMContentLoaded", initializeApp);
