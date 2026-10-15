"use strict";

const configuredApiBaseUrl =
    window.CLINICFINDER_CONFIG &&
    typeof window.CLINICFINDER_CONFIG.apiBaseUrl === "string"
        ? window.CLINICFINDER_CONFIG.apiBaseUrl
        : "http://127.0.0.1:8000";
const API_BASE_URL = configuredApiBaseUrl.replace(/\/+$/, "");
const HEALTH_ENDPOINT = `${API_BASE_URL}/health`;
const LOCATION_ENDPOINT = `${API_BASE_URL}/locations/search`;
const LOCATION_SUGGESTIONS_ENDPOINT = `${API_BASE_URL}/locations/suggestions`;
const CLINIC_ENDPOINT = `${API_BASE_URL}/clinics/search`;

const searchForm = document.getElementById("clinic-search-form");
const locationInput = document.getElementById("location");
const queryInput = document.getElementById("search-query");
const radiusSelect = document.getElementById("radius");
const searchButton = document.getElementById("search-button");
const searchStatus = document.getElementById("search-status");
const resultsContainer = document.getElementById("clinic-results");
const locationChoices = document.getElementById("location-choices");
const locationSuggestions = document.getElementById("location-suggestions");

let isSearching = false;
let localSuggestions = [];
let selectedLocation = null;
let lastClinicSearchLocation = null;
let activeSuggestionIndex = -1;

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

function appendRetryAction() {
    if (!lastClinicSearchLocation) return;
    const retryButton = document.createElement("button");
    retryButton.type = "button";
    retryButton.className = "location-choice";
    retryButton.textContent = "Retry clinic search";
    retryButton.addEventListener("click", async () => {
        setLoading(true);
        setSearchStatus("Retrying clinic search...", "info");
        try {
            await searchClinics(lastClinicSearchLocation);
        } catch (error) {
            handleSearchError(error);
        } finally {
            setLoading(false);
        }
    });
    resultsContainer.appendChild(retryButton);
}

function clearLocationChoices() {
    locationChoices.replaceChildren();
}

function normalizeSuggestionQuery(value) {
    return value.trim().toLocaleLowerCase().replace(/\s+/g, " ");
}

function closeLocationSuggestions() {
    locationSuggestions.replaceChildren();
    locationSuggestions.hidden = true;
    locationInput.setAttribute("aria-expanded", "false");
    activeSuggestionIndex = -1;
}

function selectLocalSuggestion(suggestion) {
    selectedLocation = {
        latitude: suggestion.latitude,
        longitude: suggestion.longitude,
        display_name: `${suggestion.name}, ${suggestion.context}`
    };
    locationInput.value = suggestion.name;
    closeLocationSuggestions();
    setSearchStatus("Location selected. Search clinics to continue.", "info");
}

function renderLocalSuggestions() {
    const query = normalizeSuggestionQuery(locationInput.value);
    const exactMatches = query
        ? localSuggestions.filter((suggestion) =>
            suggestion.aliases.some((alias) =>
                normalizeSuggestionQuery(alias) === query
            )
        )
        : [];
    const matches = exactMatches.length
        ? exactMatches
        : query
            ? localSuggestions.filter((suggestion) =>
                suggestion.aliases.some((alias) =>
                    normalizeSuggestionQuery(alias).startsWith(query)
                )
            )
            : [];
    locationSuggestions.replaceChildren();
    activeSuggestionIndex = -1;
    if (!matches.length) {
        closeLocationSuggestions();
        return;
    }
    matches.forEach((suggestion, index) => {
        const option = document.createElement("button");
        option.type = "button";
        option.className = "location-suggestion";
        option.id = `location-suggestion-${index}`;
        option.setAttribute("role", "option");
        option.textContent = `${suggestion.name} — ${suggestion.context}`;
        option.addEventListener("mousedown", (event) => event.preventDefault());
        option.addEventListener("click", () => selectLocalSuggestion(suggestion));
        locationSuggestions.appendChild(option);
    });
    locationSuggestions.hidden = false;
    locationInput.setAttribute("aria-expanded", "true");
}

function moveSuggestionSelection(direction) {
    const options = locationSuggestions.querySelectorAll("[role='option']");
    if (!options.length) return;
    activeSuggestionIndex =
        (activeSuggestionIndex + direction + options.length) % options.length;
    options.forEach((option, index) => {
        option.setAttribute("aria-selected", String(index === activeSuggestionIndex));
    });
    locationInput.setAttribute(
        "aria-activedescendant",
        options[activeSuggestionIndex].id
    );
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

async function requestClinicSearch(params) {
    const response = await fetch(`${CLINIC_ENDPOINT}?${params.toString()}`, {
        method: "GET",
        headers: { Accept: "application/json" }
    });
    if (!response.ok) {
        const data = await response.json().catch(() => null);
        const error = new Error(apiErrorMessage(response, "clinic search"));
        error.sourceStatus = data && data.source_status ? data.source_status : {};
        throw error;
    }
    const data = await response.json();
    if (!data || !Array.isArray(data.items)) {
        throw new Error("The clinic search response was not in the expected format.");
    }
    return data;
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
        const context = Object.values(location.address_context || {}).join(", ");
        button.textContent = context && !location.display_name.includes(context)
            ? `${location.display_name} (${context})`
            : location.display_name;
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

function formatValue(value) {
    return typeof value === "string" && value.trim() ? value : "Not available";
}

function hasText(value) {
    return typeof value === "string" && value.trim().length > 0;
}

function formatDate(value) {
    if (!value) return null;
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString();
}

function appendDetail(card, label, value, className = "") {
    if (
        value === null ||
        value === undefined ||
        (typeof value === "string" && !hasText(value))
    ) {
        return;
    }
    const detail = document.createElement("p");
    detail.className = className;
    const strong = document.createElement("strong");
    strong.textContent = `${label}: `;
    detail.append(strong, document.createTextNode(
        hasText(value) ? value.trim() : String(value)
    ));
    card.appendChild(detail);
}

function addressStatusLabel(status) {
    return {
        complete: "Complete address",
        incomplete: "Partial address",
        unknown: "Address unavailable"
    }[status] || "Address status unavailable";
}

function verificationStatusLabel(status) {
    return {
        verified: "Verified",
        stale: "Stale — re-verification needed",
        unverified: "Unverified listing",
        pending: "Unverified listing"
    }[status] || "Verification status unknown";
}

function createClinicCard(clinic) {
    const card = document.createElement("article");
    card.className = "clinic-card";

    const header = document.createElement("div");
    header.className = "clinic-card-header";
    const name = document.createElement("h3");
    name.textContent = formatValue(clinic.name);
    const badge = document.createElement("span");
    badge.className = "verification-badge";
    badge.textContent = verificationStatusLabel(clinic.verification_status);
    header.append(name, badge);
    card.appendChild(header);

    const address = document.createElement("div");
    address.className = "clinic-detail";
    const addressTitle = document.createElement("strong");
    addressTitle.textContent = "Address";
    address.appendChild(addressTitle);
    const addressText = document.createElement("p");
    addressText.className = "address-status";
    addressText.textContent = addressStatusLabel(clinic.address_status);
    address.appendChild(addressText);
    if (hasText(clinic.address)) {
        const addressValue = document.createElement("p");
        addressValue.textContent = clinic.address.trim();
        address.appendChild(addressValue);
    }
    appendDetail(address, "Locality", clinic.locality);
    appendDetail(address, "District", clinic.district);
    appendDetail(address, "City", clinic.city);
    appendDetail(address, "PIN code", clinic.postal_code);
    card.appendChild(address);
    appendDetail(card, "Facility type", clinic.facility_type);
    const checkedDate = formatDate(
        clinic.last_verified_at || clinic.last_checked_at
    );
    appendDetail(
        card,
        clinic.verification_status === "verified" ? "Last verified" : "Last checked",
        checkedDate
    );

    const actions = document.createElement("div");
    actions.className = "clinic-actions";
    if (hasText(clinic.phone)) {
        const callLink = document.createElement("a");
        callLink.className = "button button-primary";
        callLink.href = `tel:${clinic.phone.trim()}`;
        callLink.textContent = "Call clinic";
        actions.appendChild(callLink);
    }

    if (Number.isFinite(clinic.latitude) && Number.isFinite(clinic.longitude)) {
        const mapLink = document.createElement("a");
        mapLink.className = "button button-secondary";
        mapLink.href = `https://www.openstreetmap.org/?mlat=${encodeURIComponent(clinic.latitude)}&mlon=${encodeURIComponent(clinic.longitude)}#map=18/${encodeURIComponent(clinic.latitude)}/${encodeURIComponent(clinic.longitude)}`;
        mapLink.target = "_blank";
        mapLink.rel = "noopener noreferrer";
        mapLink.textContent = "View on map";
        actions.appendChild(mapLink);
    }
    card.appendChild(actions);

    appendDetail(card, "Phone", clinic.phone);
    if (hasText(clinic.website)) {
        const website = document.createElement("p");
        website.className = "clinic-detail";
        website.append("Website: ");
        const websiteLink = document.createElement("a");
        websiteLink.href = clinic.website.trim();
        websiteLink.target = "_blank";
        websiteLink.rel = "noopener noreferrer";
        websiteLink.textContent = clinic.website.trim();
        website.appendChild(websiteLink);
        card.appendChild(website);
    }
    appendDetail(
        card,
        "Distance",
        clinic.distance_km === null || clinic.distance_km === undefined
            ? null
            : `${clinic.distance_km} km`
    );

    const information = document.createElement("div");
    information.className = "clinic-information-grid";
    const doctors = Array.isArray(clinic.doctors)
        ? clinic.doctors.filter(hasText)
        : [];
    const services = Array.isArray(clinic.services)
        ? clinic.services.filter(hasText)
        : [];
    appendDetail(
        information,
        "Doctors",
        doctors.length ? doctors.join(", ") : null
    );
    appendDetail(
        information,
        "Patient reviews and rating",
        clinic.rating === null || clinic.rating === undefined
            ? null
            : String(clinic.rating)
    );
    appendDetail(
        information,
        "Services",
        services.length
            ? `${services.join(", ")} (provider data; not verified)`
            : null
    );
    if (information.childElementCount > 0) {
        card.appendChild(information);
    }

    const source = document.createElement("p");
    source.className = "clinic-disclaimer";
    const providerIdentity = clinic.source_type === "directory"
        ? "ClinicFinder directory branch"
        : `OSM ${clinic.source_type} ${clinic.source_id}`;
    source.textContent =
        `Source: ${(clinic.data_sources || []).join(", ") || "Unknown"}; ${providerIdentity}.`;
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
    lastClinicSearchLocation = location;
    const radiusKm = getRadius();
    const params = new URLSearchParams({
        latitude: String(location.latitude),
        longitude: String(location.longitude),
        radius_km: String(radiusKm)
    });
    const result = await requestClinicSearch(params);
    const clinics = result.items;
    renderClinics(clinics);
    const sourceStatus = result.source_status || {};
    if (result.result_status === "partial") {
        setSearchStatus(
            `${clinics.length} clinic listing(s) found. Some supplementary sources were unavailable.`,
            "info"
        );
        appendRetryAction();
        return;
    }
    setSearchStatus(
        clinics.length
            ? `${clinics.length} clinic listing(s) found near the selected approximate area.`
            : "No clinic listings were found for the selected approximate area.",
        clinics.length ? "success" : "info"
    );
    if (
        result.result_status === "no_matches" &&
        sourceStatus.overpass === "unavailable"
    ) {
        setSearchStatus(
            "No verified clinics matched this radius. The supplementary map source was unavailable; retry to check it.",
            "info"
        );
        appendRetryAction();
    }
}

function handleSearchError(error) {
    console.error("Clinic search failed:", error);
    setSearchStatus(error.message, "error");
    showMessage(error.message);
    if (error.sourceStatus && error.sourceStatus.overpass === "unavailable") {
        setSearchStatus(
            "All clinic sources are currently unavailable. Please retry shortly.",
            "error"
        );
        appendRetryAction();
    }
}

async function handleSearch(event) {
    event.preventDefault();
    if (isSearching) {
        return;
    }

    clearLocationChoices();
    closeLocationSuggestions();
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
    setSearchStatus(
        selectedLocation ? "Searching the selected location..." : "Finding the selected area...",
        "info"
    );
    showMessage(selectedLocation ? "Loading clinic listings..." : "Finding the approximate location...");

    try {
        if (selectedLocation) {
            await searchClinics(selectedLocation);
            return;
        }
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
        locationChoices,
        locationSuggestions
    ];
    if (requiredElements.some((element) => !element)) {
        console.error("A required HTML element is missing.");
        return;
    }

    searchForm.addEventListener("submit", handleSearch);
    locationInput.addEventListener("input", () => {
        selectedLocation = null;
        locationInput.removeAttribute("aria-activedescendant");
        renderLocalSuggestions();
    });
    locationInput.addEventListener("keydown", (event) => {
        if (event.key === "ArrowDown") {
            event.preventDefault();
            moveSuggestionSelection(1);
        } else if (event.key === "ArrowUp") {
            event.preventDefault();
            moveSuggestionSelection(-1);
        } else if (event.key === "Escape") {
            closeLocationSuggestions();
        } else if (event.key === "Enter" && activeSuggestionIndex >= 0) {
            event.preventDefault();
            const option = locationSuggestions.querySelectorAll("[role='option']")[activeSuggestionIndex];
            option.click();
        }
    });
    document.addEventListener("click", (event) => {
        if (!locationSuggestions.contains(event.target) && event.target !== locationInput) {
            closeLocationSuggestions();
        }
    });
    try {
        const [response, suggestionsResponse] = await Promise.all([
            fetch(HEALTH_ENDPOINT, { headers: { Accept: "application/json" } }),
            fetch(LOCATION_SUGGESTIONS_ENDPOINT, { headers: { Accept: "application/json" } })
        ]);
        if (suggestionsResponse.ok) {
            const data = await suggestionsResponse.json();
            localSuggestions = Array.isArray(data.items) ? data.items : [];
        }
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
