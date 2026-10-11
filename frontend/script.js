"use strict";

const configuredApiBaseUrl =
    window.CLINICFINDER_CONFIG &&
    typeof window.CLINICFINDER_CONFIG.apiBaseUrl === "string"
        ? window.CLINICFINDER_CONFIG.apiBaseUrl
        : "http://127.0.0.1:8000";
const API_BASE_URL = configuredApiBaseUrl.replace(/\/+$/, "");
const HEALTH_ENDPOINT = `${API_BASE_URL}/health`;
const LOCATION_ENDPOINT = `${API_BASE_URL}/locations/search`;
const CLINIC_ENDPOINT = `${API_BASE_URL}/clinics/search`;

const searchForm = document.getElementById("clinic-search-form");
const locationInput = document.getElementById("location");
const queryInput = document.getElementById("search-query");
const radiusSelect = document.getElementById("radius");
const searchButton = document.getElementById("search-button");
const searchStatus = document.getElementById("search-status");
const resultsContainer = document.getElementById("clinic-results");
const locationChoices = document.getElementById("location-choices");

let isSearching = false;

function setSearchStatus(message, type = "info") {
    searchStatus.textContent = message;
    searchStatus.dataset.type = type;
}

function setLoading(loading) {
    isSearching = loading;
    searchButton.disabled = loading;
    searchButton.textContent = loading ? "Searching..." : "Search clinics";
    resultsContainer.setAttribute("aria-busy", String(loading));
}

function showMessage(message, className = "empty-state") {
    resultsContainer.replaceChildren();
    const paragraph = document.createElement("p");
    paragraph.className = className;
    paragraph.textContent = message;
    resultsContainer.appendChild(paragraph);
}

function clearLocationChoices() {
    locationChoices.replaceChildren();
}

function validateLocationQuery() {
    const query = locationInput.value.trim();
    if (query.length < 2 || query.length > 200) {
        throw new Error("Enter an area or address between 2 and 200 characters.");
    }
    return query;
}

function getRadius() {
    const radiusKm = Number(radiusSelect.value);
    if (!Number.isFinite(radiusKm) || radiusKm <= 0 || radiusKm > 50) {
        throw new Error("Select a search distance between 0 and 50 km.");
    }
    return radiusKm;
}

function apiErrorMessage(response, subject) {
    if (response.status === 503) {
        return `The ${subject} provider is temporarily unavailable. Please try again later.`;
    }
    if (response.status === 502) {
        return `The ${subject} provider returned an invalid response. Please try again later.`;
    }
    if (response.status === 422) {
        return `The ${subject} input is invalid.`;
    }
    return `The ${subject} request could not be completed. Please try again.`;
}

async function requestJson(endpoint, params, subject) {
    const response = await fetch(`${endpoint}?${params.toString()}`, {
        method: "GET",
        headers: { Accept: "application/json" }
    });
    if (!response.ok) {
        throw new Error(apiErrorMessage(response, subject));
    }
    const data = await response.json();
    if (!data || !Array.isArray(data.items)) {
        throw new Error(`The ${subject} response was not in the expected format.`);
    }
    return data.items;
}

function renderLocationChoices(locations) {
    clearLocationChoices();
    const heading = document.createElement("p");
    heading.className = "field-hint";
    heading.textContent = "Several locations matched. Select the intended area:";
    locationChoices.appendChild(heading);

    locations.forEach((location, index) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "location-choice";
        button.textContent = location.display_name;
        button.addEventListener("click", () => {
            clearLocationChoices();
            setLoading(true);
            setSearchStatus("Searching the selected approximate area...", "info");
            showMessage("Loading clinic listings...");
            searchClinics(location).catch(handleSearchError).finally(() => {
                setLoading(false);
            });
        });
        button.setAttribute("aria-label", `Select location ${index + 1}`);
        locationChoices.appendChild(button);
    });
}

function formatOptional(label, value) {
    if (typeof value !== "string" || value.trim() === "") {
        return null;
    }
    const paragraph = document.createElement("p");
    paragraph.textContent = `${label}: ${value}`;
    return paragraph;
}

function createClinicCard(clinic) {
    const card = document.createElement("article");
    card.className = "clinic-card";

    const badge = document.createElement("p");
    badge.className = "unverified-badge";
    badge.textContent = "OPENSTREETMAP LISTING — NOT VERIFIED";

    const name = document.createElement("h3");
    name.textContent = clinic.name;
    card.append(badge, name);

    [
        formatOptional("Address", clinic.address),
        formatOptional("Phone", clinic.phone),
        formatOptional("Website", clinic.website),
        clinic.services && clinic.services.length
            ? formatOptional("Services", clinic.services.join(", "))
            : null,
        clinic.distance_km !== null && clinic.distance_km !== undefined
            ? formatOptional("Distance", `${clinic.distance_km} km`)
            : null
    ].forEach((element) => {
        if (element) {
            card.appendChild(element);
        }
    });

    if (Number.isFinite(clinic.latitude) && Number.isFinite(clinic.longitude)) {
        const mapLink = document.createElement("a");
        mapLink.href =
            `https://www.openstreetmap.org/?mlat=${encodeURIComponent(
                clinic.latitude
            )}&mlon=${encodeURIComponent(clinic.longitude)}#map=18/` +
            `${encodeURIComponent(clinic.latitude)}/${encodeURIComponent(
                clinic.longitude
            )}`;
        mapLink.target = "_blank";
        mapLink.rel = "noopener noreferrer";
        mapLink.textContent = "View location on OpenStreetMap";
        card.appendChild(mapLink);
    }

    const source = document.createElement("p");
    source.className = "clinic-disclaimer";
    source.textContent =
        `Source: ${(clinic.data_sources || []).join(", ") || "Unknown"}; ` +
        `OSM ${clinic.source_type} ${clinic.source_id}.`;
    card.appendChild(source);
    return card;
}

function renderClinics(clinics) {
    resultsContainer.replaceChildren();
    if (clinics.length === 0) {
        showMessage("No clinic listings were returned for this approximate area.");
        return;
    }
    const fragment = document.createDocumentFragment();
    clinics.forEach((clinic) => {
        fragment.appendChild(createClinicCard(clinic));
    });
    resultsContainer.appendChild(fragment);
}

async function searchClinics(location) {
    const radiusKm = getRadius();
    const params = new URLSearchParams({
        latitude: String(location.latitude),
        longitude: String(location.longitude),
        radius_km: String(radiusKm)
    });
    const clinics = await requestJson(CLINIC_ENDPOINT, params, "clinic search");
    renderClinics(clinics);
    setSearchStatus(
        clinics.length
            ? `${clinics.length} unverified clinic listing(s) found near the selected approximate area.`
            : "No clinic listings were found for the selected approximate area.",
        clinics.length ? "success" : "info"
    );
}

function handleSearchError(error) {
    console.error("Clinic search failed:", error);
    setSearchStatus(error.message, "error");
    showMessage(error.message);
}

async function handleSearch(event) {
    event.preventDefault();
    if (isSearching) {
        return;
    }

    clearLocationChoices();
    let query;
    try {
        query = validateLocationQuery();
        getRadius();
    } catch (error) {
        setSearchStatus(error.message, "error");
        showMessage("Please correct the form and try again.");
        return;
    }

    setLoading(true);
    setSearchStatus("Finding the selected area...", "info");
    showMessage("Finding the approximate location...");

    try {
        const params = new URLSearchParams({ query });
        const locations = await requestJson(
            LOCATION_ENDPOINT,
            params,
            "location search"
        );
        if (locations.length === 0) {
            setSearchStatus("No matching locations were found.", "error");
            showMessage("No matching locations were found. Try a more specific area name.");
            return;
        }
        if (locations.length > 1) {
            renderLocationChoices(locations);
            setSearchStatus("Select the intended location before searching clinics.", "info");
            showMessage("Choose a location from the matches above.");
            return;
        }
        await searchClinics(locations[0]);
    } catch (error) {
        handleSearchError(error);
    } finally {
        setLoading(false);
    }
}

async function initializeApp() {
    const requiredElements = [
        searchForm,
        locationInput,
        queryInput,
        radiusSelect,
        searchButton,
        searchStatus,
        resultsContainer,
        locationChoices
    ];
    if (requiredElements.some((element) => !element)) {
        console.error("A required HTML element is missing.");
        return;
    }

    searchForm.addEventListener("submit", handleSearch);
    try {
        const response = await fetch(HEALTH_ENDPOINT, {
            headers: { Accept: "application/json" }
        });
        setSearchStatus(
            response.ok
                ? "Backend connected. Enter an area to search live listings."
                : "Backend health check failed. Search may be unavailable.",
            response.ok ? "success" : "error"
        );
    } catch (error) {
        console.warn("Backend health check failed:", error.message);
        setSearchStatus(
            "Backend is not reachable. Start FastAPI before searching.",
            "error"
        );
    }
}

document.addEventListener("DOMContentLoaded", initializeApp);
