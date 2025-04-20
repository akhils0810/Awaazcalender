document.addEventListener('DOMContentLoaded', function() {
    const shiftHours = {
        'A1': 8, 'A2': 4, 'A3': 8, 'G': 8,
        'B1': 8, 'B2': 8, 'B3': 8
    };

    function updateCaregiverHours() {
        const caregiverHours = {};
        
        // Initialize hours for all caregivers
        document.querySelectorAll('#caregiver-hours .card').forEach(card => {
            const name = card.querySelector('.card-title').textContent;
            caregiverHours[name] = 0;
        });

        // Calculate hours from selected shifts
        document.querySelectorAll('.shift-select').forEach(select => {
            if (select.value) {
                const caregiverName = select.options[select.selectedIndex].text;
                caregiverHours[caregiverName] = (caregiverHours[caregiverName] || 0) + shiftHours[select.dataset.shift];
            }
        });

        // Update the display
        for (const [name, hours] of Object.entries(caregiverHours)) {
            const card = document.querySelector(`#caregiver-hours .card-title:contains('${name}')`).closest('.card');
            const hoursSpan = card.querySelector('.hours');
            hoursSpan.textContent = hours;

            // Highlight if over 40 hours
            if (hours > 40) {
                card.classList.add('shift-warning');
            } else {
                card.classList.remove('shift-warning');
            }
        }
    }

    function checkShiftOverlap(select) {
        const day = select.dataset.day;
        const shift = select.dataset.shift;
        const caregiver = select.value;
        
        if (!caregiver) return;

        const overlappingShifts = {
            'A1': ['A2', 'A3'],
            'A2': ['A1', 'A3', 'G'],
            'A3': ['A1', 'A2', 'G', 'B1'],
            'G': ['A2', 'A3', 'B1'],
            'B1': ['A3', 'G', 'B2'],
            'B2': ['B1', 'B3'],
            'B3': ['B2']
        };

        // Remove existing warnings
        document.querySelectorAll('.shift-overlap').forEach(el => el.classList.remove('shift-overlap'));

        // Check for overlaps
        overlappingShifts[shift].forEach(overlapShift => {
            const overlapSelect = document.querySelector(`.shift-select[data-day="${day}"][data-shift="${overlapShift}"]`);
            if (overlapSelect && overlapSelect.value === caregiver) {
                select.closest('td').classList.add('shift-overlap');
                overlapSelect.closest('td').classList.add('shift-overlap');
            }
        });
    }

    // Add event listeners
    document.querySelectorAll('.shift-select').forEach(select => {
        select.addEventListener('change', function() {
            updateCaregiverHours();
            checkShiftOverlap(this);
        });
    });
});

// Helper function to make :contains case-insensitive
jQuery.expr[':'].contains = function(a, i, m) {
    return jQuery(a).text().toUpperCase()
        .indexOf(m[3].toUpperCase()) >= 0;
}; 