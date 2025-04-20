// Calendar.js - Calendar View Management

// Constants
const VIEWS = {
    HOURLY: 'hourly',
    WEEKLY: 'weekly',
    MONTHLY: 'monthly'
};

const VIEW_INTERVALS = {
    [VIEWS.HOURLY]: 3, // 3 days at a time
    [VIEWS.WEEKLY]: 7, // 7 days at a time
    [VIEWS.MONTHLY]: 28 // 28 days (4 weeks) at a time
};

const HOURS_IN_DAY = 24;
const HOUR_INTERVAL = 2; // 2-hour granularity for hourly view

// State management
let currentView = VIEWS.WEEKLY; // Default view
let currentDate = new Date();
currentDate.setHours(0, 0, 0, 0);

// DOM Elements
const viewButtons = document.querySelectorAll('.btn-view');
const viewContainers = document.querySelectorAll('.view-container');
const prevBtn = document.getElementById('prevBtn');
const nextBtn = document.getElementById('nextBtn');
const dateDisplay = document.getElementById('dateDisplay');
const dateInput = document.getElementById('dateInput');
const templateSelect = document.getElementById('templateSelect');
const monthsInput = document.getElementById('monthsInput');
const generateCalendarBtn = document.getElementById('generateCalendarBtn');
const addShiftBtn = document.getElementById('addShiftBtn');
const viewAuditBtn = document.getElementById('viewAuditBtn');
const exportIcsBtn = document.getElementById('exportIcsBtn');
const loadingOverlay = document.querySelector('.loading-overlay');

// Grid containers
const hourlyGrid = document.querySelector('.hourly-grid tbody');
const hourlyHeader = document.querySelector('.hourly-grid thead tr');
const weeklyGrid = document.querySelector('.weekly-grid tbody');
const weeklyHeader = document.querySelector('.weekly-grid thead tr');
const monthlyGrid = document.querySelector('.monthly-grid tbody');
const monthlyHeader = document.querySelector('.monthly-grid thead tr');

// Modal elements
const shiftModal = new bootstrap.Modal(document.getElementById('shiftModal'));
const shiftForm = document.getElementById('shiftForm');
const editShiftId = document.getElementById('editShiftId');
const shiftDate = document.getElementById('shiftDate');
const shiftType = document.getElementById('shiftType');
const shiftCaregiver = document.getElementById('shiftCaregiver');
const shiftStart = document.getElementById('shiftStart');
const shiftEnd = document.getElementById('shiftEnd');
const saveShiftBtn = document.getElementById('saveShiftBtn');
const deleteShiftBtn = document.getElementById('deleteShiftBtn');

// Event Listeners
viewButtons.forEach(button => {
    button.addEventListener('click', () => {
        const view = button.dataset.view;
        switchView(view);
    });
});

prevBtn.addEventListener('click', () => {
    navigatePrevious();
});

nextBtn.addEventListener('click', () => {
    navigateNext();
});

dateInput.addEventListener('change', () => {
    currentDate = new Date(dateInput.value);
    updateCalendar();
});

templateSelect.addEventListener('change', function() {
    // Just selecting a template doesn't do anything until generate is clicked
});

generateCalendarBtn.addEventListener('click', () => {
    const templateId = templateSelect.value;
    if (!templateId) {
        alert('Please select a template first');
        return;
    }
    
    const months = parseInt(monthsInput.value) || 3;
    if (months < 1 || months > 12) {
        alert('Months must be between 1 and 12');
        return;
    }
    
    generateCalendar(templateId, months);
});

addShiftBtn.addEventListener('click', () => {
    showAddShiftModal();
});

viewAuditBtn.addEventListener('click', () => {
    window.location.href = '/audit';
});

exportIcsBtn.addEventListener('click', () => {
    exportCalendar();
});

saveShiftBtn.addEventListener('click', saveShift);
deleteShiftBtn.addEventListener('click', deleteShift);
shiftType.addEventListener('change', updateShiftTimes);

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    // Set default view from URL param if present
    const urlParams = new URLSearchParams(window.location.search);
    const viewParam = urlParams.get('view');
    if (viewParam && Object.values(VIEWS).includes(viewParam)) {
        currentView = viewParam;
    }
    
    // Default to today's date
    dateInput.value = formatDateForInput(currentDate);
    
    // Initialize the view
    switchView(currentView);
});

// View Management Functions
function switchView(view) {
    if (!Object.values(VIEWS).includes(view)) {
        console.error('Invalid view:', view);
        return;
    }
    
    currentView = view;
    
    // Update active button
    viewButtons.forEach(btn => {
        btn.classList.toggle('active', btn.dataset.view === view);
        btn.classList.toggle('btn-outline-primary', btn.dataset.view !== view);
        btn.classList.toggle('btn-primary', btn.dataset.view === view);
    });
    
    // Update visible container
    viewContainers.forEach(container => {
        container.classList.toggle('active', container.id === `${view}View`);
    });
    
    // Update the calendar display
    updateCalendar();
    
    // Update URL without reloading
    const url = new URL(window.location);
    url.searchParams.set('view', view);
    window.history.pushState({}, '', url);
}

function updateCalendar() {
    // Update date display
    updateDateDisplay();
    
    // Render appropriate view
    switch (currentView) {
        case VIEWS.HOURLY:
            renderHourlyView();
            break;
        case VIEWS.WEEKLY:
            renderWeeklyView();
            break;
        case VIEWS.MONTHLY:
            renderMonthlyView();
            break;
    }
}

function navigatePrevious() {
    const days = VIEW_INTERVALS[currentView];
    currentDate.setDate(currentDate.getDate() - days);
    dateInput.value = formatDateForInput(currentDate);
    updateCalendar();
}

function navigateNext() {
    const days = VIEW_INTERVALS[currentView];
    currentDate.setDate(currentDate.getDate() + days);
    dateInput.value = formatDateForInput(currentDate);
    updateCalendar();
}

function updateDateDisplay() {
    const interval = VIEW_INTERVALS[currentView];
    const endDate = new Date(currentDate);
    endDate.setDate(endDate.getDate() + interval - 1);
    
    let displayText = '';
    
    if (currentView === VIEWS.MONTHLY) {
        // For monthly view, show month and year
        displayText = `${currentDate.toLocaleDateString('en-US', { month: 'long', year: 'numeric' })}`;
    } else {
        // For other views, show date range
        displayText = `${formatDateDisplay(currentDate)} - ${formatDateDisplay(endDate)}`;
    }
    
    dateDisplay.textContent = displayText;
}

// Helper Functions
function formatDateForInput(date) {
    return date.toISOString().split('T')[0];
}

function formatDateDisplay(date) {
    return date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric'
    });
}

function formatTimeDisplay(hour, minute = 0) {
    return `${hour.toString().padStart(2, '0')}:${minute.toString().padStart(2, '0')}`;
}

function showLoading() {
    loadingOverlay.style.display = 'flex';
}

function hideLoading() {
    loadingOverlay.style.display = 'none';
}

function isToday(date) {
    const today = new Date();
    return date.getDate() === today.getDate() && 
           date.getMonth() === today.getMonth() && 
           date.getFullYear() === today.getFullYear();
}

function isWeekend(date) {
    const day = date.getDay();
    return day === 0 || day === 6; // 0 is Sunday, 6 is Saturday
}

function getWeekStart(date) {
    const result = new Date(date);
    const day = result.getDay();
    const diff = result.getDate() - day + (day === 0 ? -6 : 1); // adjust when day is Sunday
    result.setDate(diff);
    return result;
}

function updateShiftTimes() {
    const shiftDefinitions = {
        'A1': {'start': '00:01', 'end': '08:00'},
        'A2': {'start': '06:00', 'end': '10:00'},
        'A3': {'start': '06:00', 'end': '14:00'},
        'G': {'start': '10:00', 'end': '18:00'},
        'B1': {'start': '14:00', 'end': '22:00'},
        'B2': {'start': '16:00', 'end': '23:59'},
        'B3': {'start': '18:00', 'end': '22:00'}
    };
    
    const selected = shiftType.value;
    if (selected && shiftDefinitions[selected]) {
        shiftStart.value = shiftDefinitions[selected].start;
        shiftEnd.value = shiftDefinitions[selected].end;
    }
}

// Load shifts for the current date range based on view
function loadShifts(view) {
    // Calculate date range based on view
    const days = VIEW_INTERVALS[view];
    const startDate = formatDateForInput(currentDate);
    const endDate = new Date(currentDate);
    endDate.setDate(endDate.getDate() + days - 1);
    const endDateStr = formatDateForInput(endDate);
    
    // Fetch shifts from API
    fetch(`/api/shifts?start=${startDate}&end=${endDateStr}`)
        .then(response => {
            if (!response.ok) {
                return response.json().then(data => {
                    throw new Error(data.error || 'Failed to load shifts');
                });
            }
            return response.json();
        })
        .then(shifts => {
            // Render shifts based on the current view
            switch (view) {
                case VIEWS.HOURLY:
                    renderHourlyShifts(shifts);
                    break;
                case VIEWS.WEEKLY:
                    renderWeeklyShifts(shifts);
                    break;
                case VIEWS.MONTHLY:
                    renderMonthlyShifts(shifts);
                    break;
            }
        })
        .catch(error => {
            console.error('Error loading shifts:', error);
            alert('Failed to load shifts: ' + error.message);
        })
        .finally(() => {
            hideLoading();
        });
}

// Render shifts on the hourly view
function renderHourlyShifts(shifts) {
    // Clear any existing shift items
    document.querySelectorAll('.shift-item').forEach(el => el.remove());
    
    shifts.forEach(shift => {
        // Calculate position and height
        const startDate = new Date(shift.start);
        const endDate = new Date(shift.end);
        
        // Skip shifts that don't belong in our date range
        const dayDiff = Math.floor((startDate - currentDate) / (24 * 60 * 60 * 1000));
        if (dayDiff < 0 || dayDiff >= VIEW_INTERVALS[VIEWS.HOURLY]) {
            return;
        }
        
        // Calculate grid positions
        const startHour = startDate.getHours();
        const startMinute = startDate.getMinutes();
        const endHour = endDate.getHours();
        const endMinute = endDate.getMinutes();
        
        const startTotalMinutes = startHour * 60 + startMinute;
        const endTotalMinutes = endHour * 60 + endMinute;
        let durationMinutes = endTotalMinutes - startTotalMinutes;
        
        // Handle overnight shifts
        if (durationMinutes <= 0) {
            durationMinutes += 24 * 60;
        }
        
        // Find the row for this shift
        const rowStartHour = Math.floor(startHour / HOUR_INTERVAL) * HOUR_INTERVAL;
        const shiftDateStr = formatDateForInput(startDate);
        
        const cells = Array.from(document.querySelectorAll(`.shift-cell[data-date="${shiftDateStr}"]`))
            .filter(cell => parseInt(cell.dataset.hour) === rowStartHour);
        
        if (cells.length === 0) return;
        
        // Calculate top offset within the cell (percentage)
        const startOffsetPercent = ((startHour - rowStartHour) * 60 + startMinute) / (HOUR_INTERVAL * 60) * 100;
        
        // Calculate height (percentage of cell height)
        const heightPercent = Math.min(durationMinutes / (HOUR_INTERVAL * 60) * 100, 98);
        
        // Create shift item element
        const shiftItem = document.createElement('div');
        shiftItem.className = 'shift-item';
        shiftItem.dataset.shiftId = shift.id;
        shiftItem.style.backgroundColor = shift.color || '#3788d8';
        shiftItem.style.top = `${startOffsetPercent}%`;
        shiftItem.style.height = `${heightPercent}%`;
        
        // Get caregiver initials for display
        let initials = 'XX';
        if (shift.caregiver_name) {
            const nameParts = shift.caregiver_name.split(' ');
            if (nameParts.length > 1) {
                initials = `${nameParts[0][0]}${nameParts[nameParts.length - 1][0]}`;
            } else if (nameParts[0].length >= 2) {
                initials = `${nameParts[0][0]}${nameParts[0][nameParts[0].length - 1]}`;
            }
        }
        
        // Set content
        shiftItem.innerHTML = `<span class="initials">${initials}</span> ${shift.shift_type}`;
        
        // Add click handler for editing
        shiftItem.addEventListener('click', (e) => {
            e.stopPropagation();
            editShift(shift.id);
        });
        
        // Add to the cell
        cells[0].appendChild(shiftItem);
    });
}

function renderWeeklyView() {
    showLoading();
    
    // Clear existing table
    while (weeklyGrid.firstChild) {
        weeklyGrid.removeChild(weeklyGrid.firstChild);
    }
    
    // Reset header row (keep time column)
    while (weeklyHeader.children.length > 1) {
        weeklyHeader.removeChild(weeklyHeader.lastChild);
    }
    
    // Calculate the week start (Monday)
    const weekStart = getWeekStart(currentDate);
    
    // Create day headers
    for (let i = 0; i < 7; i++) {
        const date = new Date(weekStart);
        date.setDate(date.getDate() + i);
        
        const th = document.createElement('th');
        th.className = 'day-header';
        th.innerHTML = `
            <div class="day-header-name">${date.toLocaleDateString('en-US', {weekday: 'short'})}</div>
            <div class="day-header-date">${date.toLocaleDateString('en-US', {month: 'short', day: 'numeric'})}</div>
        `;
        
        // Add special classes
        if (isToday(date)) {
            th.classList.add('today');
        }
        if (isWeekend(date)) {
            th.classList.add('weekend');
        }
        
        weeklyHeader.appendChild(th);
    }
    
    // Create time rows - using 2-hour intervals for consistency with hourly view
    for (let hour = 0; hour < HOURS_IN_DAY; hour += HOUR_INTERVAL) {
        const row = document.createElement('tr');
        
        // Time label column
        const timeCell = document.createElement('td');
        timeCell.className = 'time-column';
        timeCell.textContent = `${hour.toString().padStart(2, '0')}:00-${(hour + HOUR_INTERVAL).toString().padStart(2, '0')}:00`;
        row.appendChild(timeCell);
        
        // Create cells for each day
        for (let day = 0; day < 7; day++) {
            const date = new Date(weekStart);
            date.setDate(date.getDate() + day);
            
            const cell = document.createElement('td');
            cell.className = 'shift-cell';
            cell.dataset.date = formatDateForInput(date);
            cell.dataset.hour = hour;
            
            // Add special classes
            if (isToday(date)) {
                cell.classList.add('today');
            }
            if (isWeekend(date)) {
                cell.classList.add('weekend');
            }
            
            // Add click handler for adding shifts
            cell.addEventListener('click', (e) => {
                // Only handle clicks on the cell itself, not on shift items
                if (e.target === cell) {
                    editShiftId.value = '';
                    shiftDate.value = cell.dataset.date;
                    
                    // Set time based on clicked hour
                    const startHour = parseInt(cell.dataset.hour);
                    shiftStart.value = `${startHour.toString().padStart(2, '0')}:00`;
                    shiftEnd.value = `${(startHour + HOUR_INTERVAL).toString().padStart(2, '0')}:00`;
                    
                    // Show modal for adding
                    document.getElementById('shiftModalLabel').textContent = 'Add Shift';
                    deleteShiftBtn.style.display = 'none';
                    shiftModal.show();
                }
            });
            
            row.appendChild(cell);
        }
        
        weeklyGrid.appendChild(row);
    }
    
    // Load shifts
    loadShifts(VIEWS.WEEKLY);
}

// Render shifts on the weekly view
function renderWeeklyShifts(shifts) {
    // Similar to hourly shifts but adjusted for weekly view
    renderHourlyShifts(shifts); // Reuse the same rendering logic for now
}

function renderMonthlyView() {
    showLoading();
    
    // Clear existing table
    while (monthlyGrid.firstChild) {
        monthlyGrid.removeChild(monthlyGrid.firstChild);
    }
    
    // Reset header row (keep time column)
    while (monthlyHeader.children.length > 1) {
        monthlyHeader.removeChild(monthlyHeader.lastChild);
    }
    
    // Calculate first day of month
    const firstDay = new Date(currentDate.getFullYear(), currentDate.getMonth(), 1);
    
    // Get days of week as header
    const daysOfWeek = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
    daysOfWeek.forEach(day => {
        const th = document.createElement('th');
        th.className = 'day-header';
        th.textContent = day;
        monthlyHeader.appendChild(th);
    });
    
    // Calculate number of weeks needed (first Monday before first day to last day of month)
    const lastDay = new Date(currentDate.getFullYear(), currentDate.getMonth() + 1, 0);
    const firstMonday = new Date(firstDay);
    firstMonday.setDate(firstMonday.getDate() - (firstMonday.getDay() === 0 ? 6 : firstMonday.getDay() - 1));
    
    // Calculate weeks in the month view (at least 4, max 6)
    const weeksInView = Math.ceil((lastDay.getDate() - firstMonday.getDate() + 1) / 7);
    
    // Create week rows
    for (let week = 0; week < weeksInView; week++) {
        const row = document.createElement('tr');
        
        // Week label column
        const weekCell = document.createElement('td');
        weekCell.className = 'time-column';
        const weekStart = new Date(firstMonday);
        weekStart.setDate(weekStart.getDate() + week * 7);
        const weekEnd = new Date(weekStart);
        weekEnd.setDate(weekEnd.getDate() + 6);
        weekCell.textContent = `${weekStart.getDate()}/${weekStart.getMonth() + 1} - ${weekEnd.getDate()}/${weekEnd.getMonth() + 1}`;
        row.appendChild(weekCell);
        
        // Create cells for each day of the week
        for (let day = 0; day < 7; day++) {
            const date = new Date(firstMonday);
            date.setDate(date.getDate() + week * 7 + day);
            
            const cell = document.createElement('td');
            cell.className = 'day-cell';
            cell.dataset.date = formatDateForInput(date);
            
            // Add day number
            const dayNumber = document.createElement('div');
            dayNumber.className = 'day-number';
            dayNumber.textContent = date.getDate();
            cell.appendChild(dayNumber);
            
            // Add shift container
            const shiftsContainer = document.createElement('div');
            shiftsContainer.className = 'shift-container';
            cell.appendChild(shiftsContainer);
            
            // Add special classes
            if (date.getMonth() !== currentDate.getMonth()) {
                cell.classList.add('other-month');
            }
            if (isToday(date)) {
                cell.classList.add('today');
            }
            if (isWeekend(date)) {
                cell.classList.add('weekend');
            }
            
            // Add click handler for adding shifts
            cell.addEventListener('click', (e) => {
                // Only handle clicks on the cell itself or its direct children
                if (e.target === cell || e.target === dayNumber || e.target === shiftsContainer) {
                    editShiftId.value = '';
                    shiftDate.value = cell.dataset.date;
                    
                    // Set default times
                    shiftType.value = 'A3'; // Default shift type
                    updateShiftTimes();
                    
                    // Show modal for adding
                    document.getElementById('shiftModalLabel').textContent = 'Add Shift';
                    deleteShiftBtn.style.display = 'none';
                    shiftModal.show();
                }
            });
            
            row.appendChild(cell);
        }
        
        monthlyGrid.appendChild(row);
    }
    
    // Load shifts
    loadShifts(VIEWS.MONTHLY);
}

// Render shifts on the monthly view
function renderMonthlyShifts(shifts) {
    // Clear existing shift badges
    document.querySelectorAll('.shift-badge').forEach(el => el.remove());
    
    // Group shifts by date
    const shiftsByDate = {};
    
    shifts.forEach(shift => {
        const startDate = new Date(shift.start);
        const dateStr = formatDateForInput(startDate);
        
        if (!shiftsByDate[dateStr]) {
            shiftsByDate[dateStr] = [];
        }
        
        shiftsByDate[dateStr].push(shift);
    });
    
    // Render shift badges for each date
    for (const [dateStr, dateShifts] of Object.entries(shiftsByDate)) {
        const cell = document.querySelector(`.day-cell[data-date="${dateStr}"]`);
        if (!cell) continue;
        
        const shiftsContainer = cell.querySelector('.shift-container');
        
        // Show up to 3 shifts directly, then add a +X badge
        const maxVisibleShifts = 3;
        const visibleShifts = dateShifts.slice(0, maxVisibleShifts);
        
        visibleShifts.forEach(shift => {
            const shiftBadge = document.createElement('div');
            shiftBadge.className = 'shift-badge';
            shiftBadge.dataset.shiftId = shift.id;
            shiftBadge.style.backgroundColor = shift.color || '#3788d8';
            
            // Get caregiver initials
            let initials = 'XX';
            if (shift.caregiver_name) {
                const nameParts = shift.caregiver_name.split(' ');
                if (nameParts.length > 1) {
                    initials = `${nameParts[0][0]}${nameParts[nameParts.length - 1][0]}`;
                } else if (nameParts[0].length >= 2) {
                    initials = `${nameParts[0][0]}${nameParts[0][nameParts[0].length - 1]}`;
                }
            }
            
            shiftBadge.textContent = `${initials} ${shift.shift_type}`;
            
            // Add click handler for editing
            shiftBadge.addEventListener('click', (e) => {
                e.stopPropagation();
                editShift(shift.id);
            });
            
            shiftsContainer.appendChild(shiftBadge);
        });
        
        // Add a +X badge if there are more shifts
        if (dateShifts.length > maxVisibleShifts) {
            const extraShifts = dateShifts.length - maxVisibleShifts;
            const moreBadge = document.createElement('div');
            moreBadge.className = 'shift-badge more-shifts';
            moreBadge.textContent = `+${extraShifts} more`;
            
            // Add click handler to show all shifts in a popup
            moreBadge.addEventListener('click', (e) => {
                e.stopPropagation();
                
                // For this implementation, just open the first extra shift for editing
                // In a real implementation, you'd show a popup with all shifts
                if (dateShifts.length > maxVisibleShifts) {
                    editShift(dateShifts[maxVisibleShifts].id);
                }
            });
            
            shiftsContainer.appendChild(moreBadge);
        }
    }
}

function showAddShiftModal() {
    // Reset form for adding a new shift
    editShiftId.value = '';
    shiftDate.value = formatDateForInput(currentDate);
    shiftType.value = 'A3'; // Default shift type
    
    // Set default times based on shift type
    updateShiftTimes();
    
    // Show modal for adding
    document.getElementById('shiftModalLabel').textContent = 'Add Shift';
    deleteShiftBtn.style.display = 'none';
    shiftModal.show();
}

// Edit an existing shift
function editShift(shiftId) {
    // Fetch shift details
    fetch(`/api/shifts/${shiftId}`)
        .then(response => {
            if (!response.ok) {
                return response.json().then(data => {
                    throw new Error(data.error || 'Failed to load shift');
                });
            }
            return response.json();
        })
        .then(shift => {
            // Fill form with shift data
            editShiftId.value = shift.id;
            
            const startDate = new Date(shift.start);
            shiftDate.value = formatDateForInput(startDate);
            shiftType.value = shift.shift_type;
            shiftCaregiver.value = shift.caregiver_id;
            
            // Set times
            const startHour = startDate.getHours();
            const startMinute = startDate.getMinutes();
            shiftStart.value = `${startHour.toString().padStart(2, '0')}:${startMinute.toString().padStart(2, '0')}`;
            
            const endDate = new Date(shift.end);
            const endHour = endDate.getHours();
            const endMinute = endDate.getMinutes();
            shiftEnd.value = `${endHour.toString().padStart(2, '0')}:${endMinute.toString().padStart(2, '0')}`;
            
            // Show modal for editing
            document.getElementById('shiftModalLabel').textContent = 'Edit Shift';
            deleteShiftBtn.style.display = 'block';
            shiftModal.show();
        })
        .catch(error => {
            console.error('Error loading shift:', error);
            alert('Failed to load shift details: ' + error.message);
        });
}

// Save a new or updated shift
function saveShift() {
    // Validate form
    if (!shiftForm.checkValidity()) {
        shiftForm.reportValidity();
        return;
    }
    
    // Prepare shift data
    const shiftData = {
        caregiver_id: shiftCaregiver.value,
        shift_type: shiftType.value,
        start: `${shiftDate.value} ${shiftStart.value}`,
        end: `${shiftDate.value} ${shiftEnd.value}`
    };
    
    // Show loading overlay
    showLoading();
    
    // Determine if this is an add or update operation
    const isUpdate = !!editShiftId.value;
    const url = isUpdate ? `/api/shifts/${editShiftId.value}` : '/api/shifts';
    const method = isUpdate ? 'PUT' : 'POST';
    
    // Send request
    fetch(url, {
        method: method,
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(shiftData)
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(data => {
                throw new Error(data.error || 'Failed to save shift');
            });
        }
        return response.json();
    })
    .then(() => {
        // Close modal and refresh
        shiftModal.hide();
        updateCalendar();
    })
    .catch(error => {
        console.error('Error saving shift:', error);
        alert('Failed to save shift: ' + error.message);
    })
    .finally(() => {
        hideLoading();
    });
}

// Delete a shift
function deleteShift() {
    if (!editShiftId.value || !confirm('Are you sure you want to delete this shift?')) {
        return;
    }
    
    // Show loading overlay
    showLoading();
    
    fetch(`/api/shifts/${editShiftId.value}`, {
        method: 'DELETE'
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(data => {
                throw new Error(data.error || 'Failed to delete shift');
            });
        }
        return response.json();
    })
    .then(() => {
        // Close modal and refresh
        shiftModal.hide();
        updateCalendar();
    })
    .catch(error => {
        console.error('Error deleting shift:', error);
        alert('Failed to delete shift: ' + error.message);
    })
    .finally(() => {
        hideLoading();
    });
}

// Export calendar to iCalendar format
function exportCalendar() {
    // Calculate date range based on view
    const days = VIEW_INTERVALS[currentView];
    const startDate = formatDateForInput(currentDate);
    const endDate = new Date(currentDate);
    endDate.setDate(endDate.getDate() + days - 1);
    const endDateStr = formatDateForInput(endDate);
    
    // Create and open the download URL
    const downloadUrl = `/api/shifts/download-ics?start=${startDate}&end=${endDateStr}`;
    window.open(downloadUrl, '_blank');
} 