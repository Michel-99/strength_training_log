if ('serviceWorker' in navigator) {
    window.addEventListener('load', async () => {
        const registrations = await navigator.serviceWorker.getRegistrations();
        await Promise.all(registrations.map((registration) => registration.unregister()));

        if ('caches' in window) {
            const keys = await caches.keys();
            await Promise.all(keys.map((key) => caches.delete(key)));
        }
    });
}

const API_BASE_URL = '';
const TOKEN_KEY = 'strength_log_token';
const EMAIL_KEY = 'strength_log_email';

const authCard = document.getElementById('auth-card');
const appShell = document.getElementById('app-shell');
const currentUser = document.getElementById('current-user');
const authForm = document.getElementById('auth-form');
const authEmail = document.getElementById('auth-email');
const authPassword = document.getElementById('auth-password');
const registerBtn = document.getElementById('register-btn');
const loginBtn = document.getElementById('login-btn');
const logoutBtn = document.getElementById('logout-btn');

const form = document.getElementById('log-form');
const logButton = document.getElementById('log-button');
const workoutList = document.getElementById('workout-list');
const loadingSpinner = document.getElementById('loading-spinner');
const exerciseInput = document.getElementById('exercise');
const setRows = document.getElementById('set-rows');
const addSetBtn = document.getElementById('add-set-btn');

const messageBox = document.getElementById('message-box');
const messageText = document.getElementById('message-text');
const offlineIndicator = document.getElementById('offline-indicator');

const exerciseSelect = document.getElementById('exercise-select');
const chartElement = document.getElementById('workout-chart');
let isOffline = !navigator.onLine;
let rangeDays = 30;
let lastAnalysis = null;
let lastExercise = '';

function toggleSection(button) {
    const targetId = button.dataset.target;
    const content = document.getElementById(targetId);
    if (!content) return;

    const isExpanded = button.getAttribute('aria-expanded') === 'true';
    button.setAttribute('aria-expanded', String(!isExpanded));
    content.classList.toggle('collapsed', isExpanded);
}

const views = {
    log: document.getElementById('view-log'),
    analysis: document.getElementById('view-analysis')
};

function showView() {
    const name = location.hash === '#/analysis' ? 'analysis' : 'log';
    Object.entries(views).forEach(([key, el]) => el.classList.toggle('hidden', key !== name));
    document.querySelectorAll('.nav-tab').forEach((tab) => {
        const active = tab.dataset.view === name;
        tab.classList.toggle('active', active);
    });
    if (name === 'analysis' && exerciseSelect.value) {
        updateChart(exerciseSelect.value);
    }
}

function initCollapsibles() {
    document.querySelectorAll('.section-toggle').forEach((button) => {
        button.addEventListener('click', () => toggleSection(button));
    });
}

function getToken() {
    return localStorage.getItem(TOKEN_KEY);
}

function setAuth(token, email) {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(EMAIL_KEY, email);
    currentUser.textContent = `Signed in as ${email}`;
    authCard.classList.add('hidden');
    appShell.classList.remove('hidden');
    fetchWorkouts();
    loadExerciseDropdown();
    loadPolarStatus();
    handlePolarRedirect();
}

function clearAuth() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(EMAIL_KEY);
    authCard.classList.remove('hidden');
    appShell.classList.add('hidden');
    workoutList.innerHTML = '';
    lastAnalysis = null;
    clearChart();
}

function clearChart() {
    d3.select(chartElement).selectAll('*').remove();
}

function filterByRange(data) {
    if (!rangeDays) return data;
    const cutoff = new Date();
    cutoff.setHours(0, 0, 0, 0);
    cutoff.setDate(cutoff.getDate() - rangeDays);
    const parse = d3.timeParse('%Y-%m-%d');
    const keep = data.labels.map((label) => parse(label) >= cutoff);
    return {
        labels: data.labels.filter((_, i) => keep[i]),
        volume: data.volume.filter((_, i) => keep[i]),
        max_weight: data.max_weight.filter((_, i) => keep[i])
    };
}

function updateRangeButtons() {
    document.querySelectorAll('.range-btn').forEach((btn) => {
        const active = Number(btn.dataset.days) === rangeDays;
        btn.classList.toggle('active', active);
    });
}

function renderChart(fullData, exerciseName) {
    clearChart();
    lastAnalysis = fullData;
    lastExercise = exerciseName;
    const data = filterByRange(fullData);

    const parseDate = d3.timeParse('%Y-%m-%d');
    const sessions = data.labels.map((label, i) => ({
        label,
        volume: Number(data.volume[i]),
        maxWeight: Number(data.max_weight[i])
    }));

    const svg = d3.select(chartElement);
    const rect = chartElement.getBoundingClientRect();
    const width = Math.max(320, Math.floor(rect.width || 320));
    const height = 280;
    const margin = { top: 44, right: 48, bottom: 36, left: 52 };

    svg.attr('viewBox', `0 0 ${width} ${height}`)
        .attr('preserveAspectRatio', 'xMidYMid meet');

    if (!sessions.length) {
        svg.append('text')
            .attr('x', width / 2)
            .attr('y', height / 2)
            .attr('text-anchor', 'middle')
            .attr('fill', '#9CA3AF')
            .attr('font-size', 14)
            .text('No sessions in this period.');
        return;
    }

    const volumeColor = '#6366F1';
    const weightColor = '#F59E0B';
    const axisStyle = (g) => g
        .call((sel) => sel.selectAll('text').attr('fill', '#9CA3AF'))
        .call((sel) => sel.selectAll('line,path').attr('stroke', '#6B7280'));

    const x = d3.scaleBand()
        .domain(sessions.map((d) => d.label))
        .range([margin.left, width - margin.right])
        .padding(0.25);
    const yVolume = d3.scaleLinear()
        .domain([0, (d3.max(sessions, (d) => d.volume) || 1) * 1.1])
        .nice()
        .range([height - margin.bottom, margin.top]);
    const yWeight = d3.scaleLinear()
        .domain([0, (d3.max(sessions, (d) => d.maxWeight) || 1) * 1.1])
        .nice()
        .range([height - margin.bottom, margin.top]);

    const labelFormat = d3.timeFormat('%b %d');
    const step = Math.ceil(sessions.length / 6);
    svg.append('g')
        .attr('transform', `translate(0,${height - margin.bottom})`)
        .call(d3.axisBottom(x)
            .tickValues(x.domain().filter((_, i) => i % step === 0))
            .tickFormat((label) => labelFormat(parseDate(label))))
        .call(axisStyle);

    svg.append('g')
        .attr('transform', `translate(${margin.left},0)`)
        .call(d3.axisLeft(yVolume).ticks(6))
        .call(axisStyle)
        .call((g) => g.selectAll('text').attr('fill', volumeColor));

    svg.append('g')
        .attr('transform', `translate(${width - margin.right},0)`)
        .call(d3.axisRight(yWeight).ticks(6))
        .call(axisStyle)
        .call((g) => g.selectAll('text').attr('fill', weightColor));

    svg.selectAll('.bar')
        .data(sessions)
        .enter()
        .append('rect')
        .attr('class', 'bar')
        .attr('x', (d) => x(d.label))
        .attr('y', (d) => yVolume(d.volume))
        .attr('width', x.bandwidth())
        .attr('height', (d) => yVolume(0) - yVolume(d.volume))
        .attr('fill', volumeColor)
        .attr('opacity', 0.8)
        .attr('rx', 3)
        .append('title')
        .text((d) => `${d.label}: ${d.volume} kg total volume`);

    const cx = (d) => x(d.label) + x.bandwidth() / 2;
    svg.append('path')
        .datum(sessions)
        .attr('fill', 'none')
        .attr('stroke', weightColor)
        .attr('stroke-width', 2)
        .attr('d', d3.line().x(cx).y((d) => yWeight(d.maxWeight)));

    svg.selectAll('.dot')
        .data(sessions)
        .enter()
        .append('circle')
        .attr('class', 'dot')
        .attr('cx', cx)
        .attr('cy', (d) => yWeight(d.maxWeight))
        .attr('r', 4)
        .attr('fill', weightColor)
        .append('title')
        .text((d) => `${d.label}: max ${d.maxWeight} kg`);

    svg.append('text')
        .attr('x', margin.left)
        .attr('y', 14)
        .attr('fill', '#D1D5DB')
        .attr('font-size', 12)
        .text(exerciseName);

    const legend = svg.append('g').attr('transform', `translate(${margin.left},28)`);
    legend.append('rect').attr('width', 10).attr('height', 10).attr('fill', volumeColor);
    legend.append('text').attr('x', 14).attr('y', 9).attr('fill', '#9CA3AF').attr('font-size', 11)
        .text('Volume (kg)');
    legend.append('circle').attr('cx', 100).attr('cy', 5).attr('r', 4).attr('fill', weightColor);
    legend.append('text').attr('x', 108).attr('y', 9).attr('fill', '#9CA3AF').attr('font-size', 11)
        .text('Max weight (kg)');
}

function showMessage(message, isError = true) {
    messageText.textContent = message;
    messageBox.className = `fixed bottom-4 right-4 text-white py-3 px-5 rounded-xl shadow-xl z-50 ${isError ? 'bg-red-600' : 'bg-emerald-600'}`;
    messageBox.classList.remove('hidden');
    setTimeout(() => messageBox.classList.add('hidden'), 3000);
}

async function apiFetch(path, options = {}) {
    const token = getToken();
    const headers = {
        ...(options.headers || {}),
        'Content-Type': 'application/json'
    };
    if (token) {
        headers.Authorization = `Bearer ${token}`;
    }

    const response = await fetch(`${API_BASE_URL}${path}`, {
        ...options,
        headers
    });

    if (response.status === 401) {
        clearAuth();
        showMessage('Your session expired. Please log in again.', true);
        throw new Error('Unauthorized');
    }

    return response;
}

async function register() {
    const payload = {
        email: authEmail.value.trim(),
        password: authPassword.value
    };

    registerBtn.disabled = true;
    try {
        const response = await apiFetch('/auth/register', {
            method: 'POST',
            body: JSON.stringify(payload)
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || 'Registration failed');
        }
        setAuth(data.access_token, data.email);
        showMessage('Account created and logged in.', false);
        authForm.reset();
    } catch (error) {
        showMessage(error.message || 'Registration failed.', true);
    } finally {
        registerBtn.disabled = false;
    }
}

async function login(event) {
    event.preventDefault();
    const payload = {
        email: authEmail.value.trim(),
        password: authPassword.value
    };

    loginBtn.disabled = true;
    try {
        const response = await apiFetch('/auth/login', {
            method: 'POST',
            body: JSON.stringify(payload)
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || 'Login failed');
        }
        setAuth(data.access_token, data.email);
        showMessage('Logged in successfully.', false);
        authForm.reset();
    } catch (error) {
        showMessage(error.message || 'Login failed.', true);
    } finally {
        loginBtn.disabled = false;
    }
}

async function fetchWorkouts() {
    if (isOffline) {
        showMessage('You are offline. Cannot load workouts.', true);
        workoutList.innerHTML = '<p class="text-center text-gray-400">Cannot load history while offline.</p>';
        return;
    }

    loadingSpinner.classList.remove('hidden');
    workoutList.innerHTML = '';
    try {
        const response = await apiFetch('/workouts');
        const workouts = await response.json();
        if (!response.ok) throw new Error('Failed to fetch workouts');

        if (workouts.length === 0) {
            workoutList.innerHTML = '<p class="text-center text-gray-400">No workouts logged yet. Get started!</p>';
        } else {
            workouts.forEach(renderWorkout);
        }
    } catch {
        workoutList.innerHTML = '<p class="text-center text-red-400">Failed to load history.</p>';
    } finally {
        loadingSpinner.classList.add('hidden');
    }
}

function renumberSetRows() {
    const rows = setRows.querySelectorAll('.set-row');
    rows.forEach((row, i) => {
        row.querySelector('.set-label').textContent = `Set ${i + 1}`;
        row.querySelector('.remove-set-btn').classList.toggle('invisible', rows.length === 1);
    });
}

function addSetRow() {
    const row = document.createElement('div');
    row.className = 'set-row flex items-end gap-3';
    const inputClass = 'form-input w-full';
    row.innerHTML = `
        <span class="set-label text-sm font-medium text-slate-300 w-12 pb-2"></span>
        <div class="flex-1">
            <label class="block text-xs text-gray-400 mb-1">Weight (kg)</label>
            <input type="number" class="set-weight ${inputClass}" step="0.5" min="0" placeholder="e.g., 60" required>
        </div>
        <div class="flex-1">
            <label class="block text-xs text-gray-400 mb-1">Reps</label>
            <input type="number" class="set-reps ${inputClass}" min="1" placeholder="e.g., 5" required>
        </div>
        <button type="button" class="remove-set-btn text-gray-400 hover:text-red-500 text-xl pb-1 px-1" aria-label="Remove set">&times;</button>
    `;
    row.querySelector('.remove-set-btn').addEventListener('click', () => {
        row.remove();
        renumberSetRows();
    });
    setRows.appendChild(row);
    renumberSetRows();
}

function resetSetRows() {
    setRows.innerHTML = '';
    addSetRow();
}

async function handleFormSubmit(event) {
    event.preventDefault();
    if (isOffline) {
        showMessage('You are offline. Cannot log workout.', true);
        return;
    }

    const workout = {
        exercise: exerciseInput.value,
        sets: [...setRows.querySelectorAll('.set-row')].map((row) => ({
            weight: parseFloat(row.querySelector('.set-weight').value),
            reps: parseInt(row.querySelector('.set-reps').value, 10)
        }))
    };

    logButton.disabled = true;
    logButton.textContent = 'Logging...';

    try {
        const response = await apiFetch('/workouts/batch', {
            method: 'POST',
            body: JSON.stringify(workout)
        });
        const newWorkouts = await response.json();
        if (!response.ok) throw new Error('Failed to log workout');

        if (workoutList.querySelector('p')) {
            workoutList.innerHTML = '';
        }
        [...newWorkouts].reverse().forEach((entry) => renderWorkout(entry, true));
        form.reset();
        resetSetRows();
        showMessage('Workout logged successfully.', false);
        loadExerciseDropdown();
    } catch {
        showMessage('Failed to log workout. Please try again.', true);
    } finally {
        logButton.disabled = false;
        logButton.textContent = 'Log Workout';
    }
}

async function deleteWorkout(id, workoutCard) {
    if (isOffline) {
        showMessage('You are offline. Cannot delete workout.', true);
        return;
    }

    const originalHeight = workoutCard.offsetHeight;
    workoutCard.style.height = `${originalHeight}px`;
    workoutCard.style.transition = 'all 0.3s ease-out';
    workoutCard.style.opacity = '0';
    workoutCard.style.transform = 'translateX(-100%)';
    workoutCard.style.padding = '0';
    workoutCard.style.margin = '0';

    setTimeout(() => {
        workoutCard.remove();
        if (workoutList.children.length === 0) {
            workoutList.innerHTML = '<p class="text-center text-gray-400">No workouts logged yet. Get started!</p>';
        }
        loadExerciseDropdown();
    }, 300);

    try {
        const response = await apiFetch(`/workouts/${id}`, { method: 'DELETE' });
        if (!response.ok) throw new Error('Failed to delete workout');
        showMessage('Workout deleted.', false);
    } catch {
        showMessage('Failed to delete on server. Please refresh.', true);
    }
}

async function loadExerciseDropdown() {
    if (isOffline) {
        exerciseSelect.innerHTML = '<option value="">Cannot load exercises offline</option>';
        return;
    }

    try {
        const response = await apiFetch('/exercises');
        const exercises = await response.json();
        if (!response.ok) throw new Error('Failed to fetch exercises');

        exerciseSelect.innerHTML = '<option value="">-- Select an exercise --</option>';
        if (exercises.length === 0) {
            exerciseSelect.innerHTML = '<option value="">-- Log a workout first --</option>';
        }

        exercises.forEach((exercise) => {
            const option = document.createElement('option');
            option.value = exercise;
            option.textContent = exercise;
            exerciseSelect.appendChild(option);
        });
    } catch {
        exerciseSelect.innerHTML = '<option value="">Error loading exercises</option>';
    }
}

async function updateChart(exerciseName) {
    if (!exerciseName) {
        clearChart();
        return;
    }
    if (isOffline) {
        showMessage('You are offline. Cannot load analysis.', true);
        return;
    }

    try {
        const response = await apiFetch(`/analysis?exercise=${encodeURIComponent(exerciseName)}`);
        const data = await response.json();
        if (!response.ok) throw new Error('Failed to fetch analysis data');

        renderChart(data, exerciseName);
    } catch {
        showMessage('Failed to load chart data.', true);
    }
}

const polarStatus = document.getElementById('polar-status');
const polarConnectBtn = document.getElementById('polar-connect-btn');
const polarSyncBtn = document.getElementById('polar-sync-btn');

async function loadPolarStatus() {
    if (isOffline) return;
    try {
        const response = await apiFetch('/polar/status');
        if (!response.ok) throw new Error();
        const status = await response.json();
        polarConnectBtn.classList.toggle('hidden', !status.configured || status.connected);
        polarSyncBtn.classList.toggle('hidden', !status.connected);
        if (!status.configured) {
            polarStatus.textContent = 'Not set up on the server yet.';
        } else if (status.connected) {
            polarStatus.textContent = status.last_synced_at
                ? `Connected. Last sync ${new Date(status.last_synced_at).toLocaleString()}`
                : 'Connected.';
        } else {
            polarStatus.textContent = 'Not connected.';
        }
    } catch {
        polarStatus.textContent = 'Could not check Polar status.';
    }
}

async function connectPolar() {
    try {
        const response = await apiFetch('/polar/connect-url');
        const data = await response.json();
        if (!response.ok) throw new Error();
        window.location.href = data.url;
    } catch {
        showMessage('Could not start the Polar connection.', true);
    }
}

async function syncPolar() {
    polarSyncBtn.disabled = true;
    polarSyncBtn.textContent = 'Syncing...';
    try {
        const response = await apiFetch('/polar/sync', { method: 'POST' });
        const counts = await response.json();
        if (!response.ok) throw new Error();
        showMessage(
            `Synced ${counts.exercises} sessions, ${counts.sleep} nights, ${counts.recovery} recovery days.`,
            false
        );
        loadPolarStatus();
    } catch {
        showMessage('Polar sync failed.', true);
    } finally {
        polarSyncBtn.disabled = false;
        polarSyncBtn.textContent = 'Sync now';
    }
}

function handlePolarRedirect() {
    const result = new URLSearchParams(location.search).get('polar');
    if (!result) return;
    history.replaceState(null, '', location.pathname + location.hash);
    if (result === 'connected') showMessage('Polar connected and synced.', false);
    else showMessage('Polar connection failed or was cancelled.', true);
}

polarConnectBtn.addEventListener('click', connectPolar);
polarSyncBtn.addEventListener('click', syncPolar);

function renderWorkout(workout, prepend = false) {
    const workoutCard = document.createElement('div');
    workoutCard.className = 'workout-card';
    const date = new Date(workout.log_date * 1000);
    const formattedDate = date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
    const formattedTime = date.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });

    workoutCard.innerHTML = `
        <div>
            <h3 class="text-lg font-semibold text-white">${workout.exercise_name}</h3>
            <p class="text-sm text-gray-300">${workout.sets} ${workout.sets === 1 ? 'set' : 'sets'} &times; ${workout.reps} reps @ ${workout.weight_kg} kg</p>
            <p class="text-xs text-gray-400 mt-1">${formattedDate}, ${formattedTime}</p>
        </div>
        <button class="delete-btn text-gray-400 hover:text-red-500 transition-all p-1 rounded-full">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
        </button>
    `;

    workoutCard.querySelector('.delete-btn').addEventListener('click', (e) => {
        e.stopPropagation();
        deleteWorkout(workout.id, workoutCard);
    });

    if (prepend) {
        workoutList.prepend(workoutCard);
    } else {
        workoutList.appendChild(workoutCard);
    }
}

function updateOnlineStatus() {
    isOffline = !navigator.onLine;
    if (isOffline) {
        offlineIndicator.classList.remove('hidden');
        logButton.disabled = true;
        logButton.textContent = 'Offline';
    } else {
        offlineIndicator.classList.add('hidden');
        logButton.disabled = false;
        logButton.textContent = 'Log Workout';
    }
}

registerBtn.addEventListener('click', register);
authForm.addEventListener('submit', login);
logoutBtn.addEventListener('click', () => {
    clearAuth();
    showMessage('Logged out.', false);
});
form.addEventListener('submit', handleFormSubmit);
addSetBtn.addEventListener('click', addSetRow);
resetSetRows();
window.addEventListener('online', updateOnlineStatus);
window.addEventListener('offline', updateOnlineStatus);
document.querySelectorAll('.range-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
        rangeDays = Number(btn.dataset.days);
        updateRangeButtons();
        if (lastAnalysis) renderChart(lastAnalysis, lastExercise);
    });
});
updateRangeButtons();
exerciseSelect.addEventListener('change', (e) => updateChart(e.target.value));

window.addEventListener('hashchange', showView);
initCollapsibles();
showView();
updateOnlineStatus();
const existingToken = getToken();
const existingEmail = localStorage.getItem(EMAIL_KEY);
if (existingToken && existingEmail) {
    setAuth(existingToken, existingEmail);
}
