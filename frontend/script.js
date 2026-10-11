

"use strict";

// ========================================
// 1. CONFIGURATION
// ========================================

const API_BASE_URL = "http://127.0.0.1:8000";
const HEALTH_ENDPOINT = `${API_BASE_URL}/health`;

// These records are fictional and exist only for UI testing.
// They are NOT real or verified clinics.
const DEMO_CLINICS = [
    {
        id: "demo-001",
        name: "Demo Clinic A",
        specialty: "General Medicine",
        area: "New Town, Kolkata",
        distanceKm: 1.2,
        homeCollection: true
    },
    {
        id: "demo-002",
        name: "Demo Clinic B",
        specialty: "Dermatology",
        area: "Salt Lake, Kolkata",
        distanceKm: 3.4,
        homeCollection: false
    },
    {
        id: "demo-003",
        name: "Demo Clinic C",
        specialty: "General Medicine",
        area: "Rajarhat, Kolkata",
        distanceKm: 6.8,
        homeCollection: true
    }
];

// Demo-only keyword mapping.
// This is not a medical diagnosis or clinical recommendation.
const DEMO_KEYWORDS = {
    "general medicine": [
        "general medicine",
        "general physician",
        "physician",
        "doctor",
        "general doctor",
        "fever",
        "cold"
    ],
    "dermatology": [
        "dermatology",
        "dermatologist",
        "skin",
        "skin doctor"
    ]
};


// ========================================
// 2. DOM ELEMENTS
// ========================================

const searchForm = document.getElementById("clinic-search-form");
const locationInput = document.getElementById("location");
const queryInput = document.getElementById("search-query");
const radiusSelect = document.getElementById("radius");
const homeCollectionSelect =
    document.getElementById("home-collection");
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

        if (data.status !== "ok") {
            throw new Error("Unexpected health response");
        }

        backendAvailable = true;

        console.info("Backend connected:", data);

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

function setLoading(loading) {
    isSearching = loading;
    searchButton.disabled = loading;

    searchButton.textContent = loading
        ? "Searching..."
        : "Search clinics";

    resultsContainer.setAttribute(
        "aria-busy",
        String(loading)
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
// 6. CREATE DEMO CLINIC CARDS
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
    area.textContent = `Demo area: ${clinic.area}`;

    const distance = document.createElement("p");
    distance.textContent =
        `Fictional demo distance: ${clinic.distanceKm} km`;

    const collection = document.createElement("p");

    collection.textContent = clinic.homeCollection
        ? "Home collection: Demo value only"
        : "Home collection: Not available in this demo record";

    const disclaimer = document.createElement("p");
    disclaimer.className = "clinic-disclaimer";
    disclaimer.textContent =
        "Fictional record. Not a real clinic or verified service.";

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
        showMessage(
            "No demo records match your filters. Try General Medicine or Dermatology."
        );
        return;
    }

    const fragment = document.createDocumentFragment();

    clinics.forEach((clinic) => {
        fragment.appendChild(createClinicCard(clinic));
    });

    resultsContainer.appendChild(fragment);
}


// ========================================
// 7. VALIDATE SEARCH INPUT
// ========================================

function getSearchCriteria() {
    const location = locationInput.value.trim();
    const query = queryInput.value.trim();
    const radiusKm = Number(radiusSelect.value);
    const homeCollection = homeCollectionSelect.value;

    if (!location || !query) {
        throw new Error(
            "Please enter your location and healthcare need."
        );
    }

    if (location.length > 200 || query.length > 1000) {
        throw new Error("Your input exceeds the permitted length.");
    }

    if (![2, 5, 10, 20].includes(radiusKm)) {
        throw new Error("Please select a valid search distance.");
    }

    if (!["any", "available", "unavailable"].includes(homeCollection)) {
        throw new Error("Please select a valid home collection option.");
    }

    return {
        location,
        query,
        radiusKm,
        homeCollection
    };
}


// ========================================
// 8. NORMALIZE AND MATCH DEMO QUERIES
// ========================================

function normalizeText(value) {
    return value
        .trim()
        .toLowerCase()
        .replace(/[^\p{L}\p{N}\s]/gu, " ")
        .replace(/\s+/g, " ");
}

function matchesDemoSpecialty(clinic, query) {
    const normalizedQuery = normalizeText(query);
    const normalizedSpecialty = normalizeText(clinic.specialty);

    // Direct specialty matching.
    if (
        normalizedSpecialty.includes(normalizedQuery) ||
        normalizedQuery.includes(normalizedSpecialty)
    ) {
        return true;
    }

    // Match explicitly configured demo keywords.
    const keywords = DEMO_KEYWORDS[normalizedSpecialty] || [];

    return keywords.some((keyword) => {
        const normalizedKeyword = normalizeText(keyword);

        return (
            normalizedQuery === normalizedKeyword ||
            normalizedQuery.includes(normalizedKeyword)
        );
    });
}


// ========================================
// 9. FILTER DEMO RECORDS
// ========================================

function searchDemoClinics(criteria) {
    return DEMO_CLINICS.filter((clinic) => {
        const specialtyMatches = matchesDemoSpecialty(
            clinic,
            criteria.query
        );

        const withinDemoRadius =
            clinic.distanceKm <= criteria.radiusKm;

        const collectionMatches =
            criteria.homeCollection === "any" ||
            (
                criteria.homeCollection === "available" &&
                clinic.homeCollection === true
            ) ||
            (
                criteria.homeCollection === "unavailable" &&
                clinic.homeCollection === false
            );

        return (
            specialtyMatches &&
            withinDemoRadius &&
            collectionMatches
        );
    });
}


// ========================================
// 10. HANDLE FORM SUBMISSION
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

        showMessage(
            "Please correct the form and try again."
        );

        return;
    }

    setLoading(true);

    setSearchStatus(
        "Checking backend connection...",
        "info"
    );

    showMessage("Preparing demo search...");

    try {
        const healthy = await checkBackendHealth();

        if (!healthy) {
            setSearchStatus(
                "Backend unavailable. Start FastAPI and try again.",
                "error"
            );

            showMessage(
                "The backend health check failed. No search was performed."
            );

            return;
        }

        // This is a local demo search, NOT a real API search.
        const clinics = searchDemoClinics(criteria);

        renderClinics(clinics);

        if (clinics.length > 0) {
            setSearchStatus(
                `Backend connected. Showing ${clinics.length} fictional demo record(s). Real clinic search is not implemented.`,
                "success"
            );
        } else {
            setSearchStatus(
                "No demo records match these filters. Real clinic search is not implemented.",
                "info"
            );
        }
    } catch (error) {
        console.error("Unexpected search error:", error);

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
// 11. INITIALIZE APPLICATION
// ========================================

async function initializeApp() {
    const requiredElements = [
        searchForm,
        locationInput,
        queryInput,
        radiusSelect,
        homeCollectionSelect,
        searchButton,
        searchStatus,
        resultsContainer
    ];

    if (requiredElements.some((element) => !element)) {
        console.error(
            "A required HTML element is missing. Check the element IDs."
        );
        return;
    }

    searchForm.addEventListener("submit", handleSearch);

    setSearchStatus(
        "Checking backend connection...",
        "info"
    );

    const healthy = await checkBackendHealth();

    if (healthy) {
        setSearchStatus(
            "Backend connected. Demo mode is active.",
            "success"
        );
    } else {
        setSearchStatus(
            "Backend is not reachable. Start FastAPI to enable demo search.",
            "error"
        );
    }
}

document.addEventListener(
    "DOMContentLoaded",
    initializeApp
);
