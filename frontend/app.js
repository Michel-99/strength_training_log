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
const weightInput = document.getElementById('weight');
const setsInput = document.getElementById('sets');
const repsInput = document.getElementById('reps');

const messageBox = document.getElementById('message-box');
const messageText = document.getElementById('message-text');
const offlineIndicator = document.getElementById('offline-indicator');

const exerciseSelect = document.getElementById('exercise-select');
const chartElement = document.getElementById('workout-chart');
let isOffline = !navigator.onLine;

function toggleSection(button) {
    const targetId = button.dataset.target;
    const content = document.getElementById(targetId);
    if (!content) return;

    const isExpanded = button.getAttribute('aria-expanded') === 'true';
    button.setAttribute('aria-expanded', String(!isExpanded));
    content.classList.toggle('collapsed', isExpanded);
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
}

function clearAuth() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(EMAIL_KEY);
    authCard.classList.remove('hidden');
    appShell.classList.add('hidden');
    workoutList.innerHTML = '';
    clearChart();
}

function clearChart() {
    d3.select(chartElement).selectAll('*').remove();
}

function renderChart(data, exerciseName) {
    clearChart();

    const parseDate = d3.timeParse('%Y-%m-%d');
    const points = data.labels.map((label, i) => ({
        date: parseDate(label),
        value: Number(data.data[i])
    })).filter((point) => point.date && Number.isFinite(point.value));

    points.sort((a, b) => a.date - b.date);

    // declare chart dimensions
    const svg = d3.select(chartElement);
    const rect = chartElement.getBoundingClientRect();
    const width = Math.max(320, Math.floor(rect.width || 320));
    const height = 280;
    const margin = { top: 24, right: 16, bottom: 36, left: 52 };

    svg.attr('viewBox', `0 0 ${width} ${height}`)
        .attr('preserveAspectRatio', 'xMidYMid meet');

    if (!points.length) {
        svg.append('text')
            .attr('x', width / 2)
            .attr('y', height / 2)
            .attr('text-anchor', 'middle')
            .attr('fill', '#9CA3AF')
            .attr('font-size', 14)
            .text('No data for this exercise yet.');
        return;
    }

    // declare x-axis as bar positions
    const x = d3.scaleBand()
        .domain(points.map((_, i) => i))
        .range([margin.left, width - margin.right])
        .padding(0.2);

    const barWidth = Math.max(4, x.bandwidth());
 
    const maxY = d3.max(points, (d) => d.value) || 0;
    const y = d3.scaleLinear()
        .domain([0, maxY > 0 ? maxY * 1.1 : 1])
        .nice()
        .range([height - margin.bottom, margin.top]);

    const labelFormat = d3.timeFormat('%b %d');
    const xAxis = d3.axisBottom(x)
        .tickValues(x.domain().filter((_, i, arr) => i % Math.ceil(arr.length / 6) === 0))
        .tickFormat((i) => labelFormat(points[i].date));
    const yAxis = d3.axisLeft(y).ticks(6);

    svg.append('g')
        .attr('transform', `translate(0,${height - margin.bottom})`)
        .call(xAxis)
        .call((g) => g.selectAll('text').attr('fill', '#9CA3AF'))
        .call((g) => g.selectAll('line,path').attr('stroke', '#6B7280'));

    svg.append('g')
        .attr('transform', `translate(${margin.left},0)`)
        .call(yAxis)
        .call((g) => g.selectAll('text').attr('fill', '#9CA3AF'))
        .call((g) => g.selectAll('line,path').attr('stroke', '#6B7280'));

    svg.selectAll('.bar')
        .data(points)
        .enter()
        .append('rect')
        .attr('class', 'bar')
        .attr('x', (_, i) => (x(i) ?? margin.left) + (x.bandwidth() - barWidth) / 2)
        .attr('y', (d) => y(d.value))
        .attr('width', barWidth)
        .attr('height', (d) => y(0) - y(d.value))
        .attr('fill', '#3B82F6')
        .attr('rx', 3)
        .attr('ry', 3);

    svg.append('text')
        .attr('x', margin.left)
        .attr('y', 14)
        .attr('fill', '#D1D5DB')
        .attr('font-size', 12)
        .text(`Weight progression (bar chart): ${exerciseName}`);
}

function showMessage(message, isError = true) {
    messageText.textContent = message;
    messageBox.className = `fixed bottom-4 right-4 text-white py-3 px-5 rounded-lg shadow-xl z-50 ${isError ? 'bg-red-600' : 'bg-green-600'}`;
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

async function handleFormSubmit(event) {
    event.preventDefault();
    if (isOffline) {
        showMessage('You are offline. Cannot log workout.', true);
        return;
    }

    const workout = {
        exercise: exerciseInput.value,
        weight: parseFloat(weightInput.value),
        sets: parseInt(setsInput.value, 10),
        reps: parseInt(repsInput.value, 10)
    };

    logButton.disabled = true;
    logButton.textContent = 'Logging...';

    try {
        const response = await apiFetch('/workouts', {
            method: 'POST',
            body: JSON.stringify(workout)
        });
        const newWorkout = await response.json();
        if (!response.ok) throw new Error('Failed to log workout');

        if (workoutList.querySelector('p')) {
            workoutList.innerHTML = '';
        }
        renderWorkout(newWorkout, true);
        form.reset();
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

function renderWorkout(workout, prepend = false) {
    const workoutCard = document.createElement('div');
    workoutCard.className = 'bg-gray-700 p-4 rounded-lg flex justify-between items-center transition-all duration-300';
    const date = new Date(workout.log_date * 1000);
    const formattedDate = date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
    const formattedTime = date.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });

    workoutCard.innerHTML = `
        <div>
            <h3 class="text-lg font-semibold text-white">${workout.exercise_name}</h3>
            <p class="text-sm text-gray-300">${workout.sets} sets &times; ${workout.reps} reps @ ${workout.weight_kg} kg</p>
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
window.addEventListener('online', updateOnlineStatus);
window.addEventListener('offline', updateOnlineStatus);
exerciseSelect.addEventListener('change', (e) => updateChart(e.target.value));

initCollapsibles();
updateOnlineStatus();
const existingToken = getToken();
const existingEmail = localStorage.getItem(EMAIL_KEY);
if (existingToken && existingEmail) {
    setAuth(existingToken, existingEmail);
}
