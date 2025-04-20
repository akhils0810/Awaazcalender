from flask import Flask, render_template, request, jsonify
from datetime import datetime, timedelta
import os
import json
import logging
from dateutil import parser, tz
from icalendar import Calendar, Event
import pytz
import uuid

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Template filter for getting initials
def get_initials(name):
    name_parts = name.split()
    if len(name_parts) > 1:
        # Use first letter of first name and last letter of last name
        return (name_parts[0][0] + name_parts[-1][-1]).upper()
    else:
        # Use first and last letter of the only name
        return (name_parts[0][0] + name_parts[0][-1]).upper()

# Day mapping constants
DAYS_MAP = {
    'Monday': 0,
    'Tuesday': 1,
    'Wednesday': 2,
    'Thursday': 3,
    'Friday': 4,
    'Saturday': 5,
    'Sunday': 6
}

def normalize_day_value(day_value):
    """
    Normalize day value to integer (0 = Monday, 6 = Sunday)
    Accepts:
    - Integer (0-6)
    - String day name ('Monday'-'Sunday')
    - String number ('0'-'6')
    Returns normalized integer 0-6
    """
    try:
        if isinstance(day_value, int):
            if 0 <= day_value <= 6:
                return day_value
            raise ValueError(f"Day integer must be 0-6, got {day_value}")
            
        if isinstance(day_value, str):
            # Try parsing as day name
            day_upper = day_value.capitalize()
            if day_upper in DAYS_MAP:
                return DAYS_MAP[day_upper]
            
            # Try parsing as number
            day_int = int(day_value)
            if 0 <= day_int <= 6:
                return day_int
            raise ValueError(f"Day integer must be 0-6, got {day_int}")
            
        raise ValueError(f"Day value must be int or string, got {type(day_value)}")
    except (ValueError, TypeError) as e:
        logger.error(f"Error normalizing day value '{day_value}': {str(e)}")
        raise ValueError(f"Invalid day value: {day_value}")

def calculate_days_to_add(template_day, start_date):
    """
    Calculate days to add to start_date to reach template_day
    Both days are in 0=Monday format
    Returns number of days to add (0-6)
    """
    start_day = start_date.weekday()
    # Calculate shortest distance between days
    days_to_add = (template_day - start_day) % 7
    return days_to_add

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.jinja_env.filters['getInitials'] = get_initials

# Data file paths
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
CAREGIVERS_FILE = os.path.join(DATA_DIR, 'caregivers.json')
SHIFTS_FILE = os.path.join(DATA_DIR, 'shifts.json')
TEMPLATES_FILE = os.path.join(DATA_DIR, 'templates.json')
NOTE_TEMPLATES_FILE = os.path.join(DATA_DIR, 'note_templates.json')
WEEK_STATES_FILE = os.path.join(DATA_DIR, 'week_states.json')
LAST_TEMPLATE_FILE = os.path.join(DATA_DIR, 'last_template.json')
AUDIT_EVENTS_FILE = os.path.join(DATA_DIR, 'audit_events.json')

# Shift definitions
SHIFT_DEFINITIONS = {
    'A1': {'start': '00:01', 'end': '08:00'},
    'A2': {'start': '06:00', 'end': '10:00'},
    'A3': {'start': '06:00', 'end': '14:00'},
    'G': {'start': '10:00', 'end': '18:00'},
    'B1': {'start': '14:00', 'end': '22:00'},
    'B2': {'start': '16:00', 'end': '23:59'},
    'B3': {'start': '18:00', 'end': '22:00'}
}

# Audit event types
AUDIT_EVENT_TYPES = {
    'SHIFT_ADDED': 'Shift Added',
    'SHIFT_MODIFIED': 'Shift Modified',
    'SHIFT_DELETED': 'Shift Deleted',
    'TEMPLATE_APPLIED': 'Template Applied', 
    'CAREGIVER_ADDED': 'Caregiver Added',
    'CAREGIVER_MODIFIED': 'Caregiver Modified',
    'CAREGIVER_DELETED': 'Caregiver Deleted'
}

# Default note template
DEFAULT_NOTE_TEMPLATE = {
    "id": "default",
    "name": "Default Shift Notes",
    "fields": [
        {
            "id": "general_notes",
            "type": "textarea",
            "label": "General Notes",
            "required": True,
            "placeholder": "Enter general notes about the shift..."
        },
        {
            "id": "incidents",
            "type": "textarea",
            "label": "Incidents/Concerns",
            "required": False,
            "placeholder": "Document any incidents or concerns..."
        },
        {
            "id": "tasks_completed",
            "type": "checklist",
            "label": "Tasks Completed",
            "required": True,
            "options": [
                "Medication administered",
                "Meals prepared",
                "Activities completed",
                "Room cleaned"
            ]
        },
        {
            "id": "next_shift_handover",
            "type": "textarea",
            "label": "Handover Notes for Next Shift",
            "required": True,
            "placeholder": "Important information for the next caregiver..."
        }
    ]
}

# Ensure data directory exists
os.makedirs(DATA_DIR, exist_ok=True)

def load_audit_events():
    """Load audit events from the JSON file."""
    try:
        if os.path.exists(AUDIT_EVENTS_FILE):
            with open(AUDIT_EVENTS_FILE, 'r') as f:
                return json.load(f)
        return []
    except Exception as e:
        logger.error(f"Error loading audit events: {str(e)}")
        return []

def save_audit_events(events):
    """Save audit events to the JSON file."""
    try:
        with open(AUDIT_EVENTS_FILE, 'w') as f:
            json.dump(events, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving audit events: {str(e)}")

def create_audit_event(event_type, user="system", details=None):
    """Create and save a new audit event."""
    try:
        events = load_audit_events()
        new_event = {
            "id": str(len(events) + 1),
            "type": event_type,
            "user": user,
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "details": details or {}
        }
        events.append(new_event)
        save_audit_events(events)
        return new_event
    except Exception as e:
        logger.error(f"Error creating audit event: {str(e)}")
        return None

def load_caregivers():
    if os.path.exists(CAREGIVERS_FILE):
        with open(CAREGIVERS_FILE, 'r') as f:
            caregivers = json.load(f)
            # Ensure each caregiver has a color
            for i, caregiver in enumerate(caregivers):
                if 'color' not in caregiver:
                    # Generate a color based on ID
                    caregiver['color'] = f'#{"".join([hex((i+1)*30)[2:].zfill(2) for _ in range(3)])}'
            save_caregivers(caregivers)  # Save the updated data
            return caregivers
    return []

def save_caregivers(caregivers):
    with open(CAREGIVERS_FILE, 'w') as f:
        json.dump(caregivers, f, indent=2)

def load_shifts():
    try:
        logger.info("Loading shifts from file")
        if os.path.exists(SHIFTS_FILE):
            with open(SHIFTS_FILE, 'r') as f:
                shifts = json.load(f)
                logger.info(f"Successfully loaded {len(shifts)} shifts")
                # Validate shift data
                for shift in shifts:
                    if not all(key in shift for key in ['id', 'caregiver_id', 'start', 'end', 'shift_type']):
                        logger.warning(f"Invalid shift data found: {shift}")
                return shifts
        logger.info("No shifts file found, returning empty list")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding shifts file: {str(e)}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error loading shifts: {str(e)}", exc_info=True)
        return []

def save_shifts(shifts):
    try:
        logger.info(f"Saving {len(shifts)} shifts to file")
        # Validate shifts before saving
        for shift in shifts:
            if not all(key in shift for key in ['id', 'caregiver_id', 'start', 'end', 'shift_type']):
                raise ValueError(f"Invalid shift data: {shift}")
            
            # Validate shift times
            try:
                start = parser.parse(shift['start'])
                end = parser.parse(shift['end'])
                
                # CRITICAL FIX: Do NOT automatically adjust dates - respect what UI sent
                # Only adjust dates if they're different AND the end time is before the start time
                start_date = start.date()
                end_date = end.date()
                
                # Only adjust if end date is actually before start date
                if end_date < start_date:
                    logger.warning(f"End date {end_date} is before start date {start_date} for shift {shift['id']} - adjusting")
                    end += timedelta(days=1)
                # For same-day shifts, check if we need to adjust for overnight
                elif end_date == start_date and end <= start:
                    # Check if this is A1 shift specifically (00:01 - 08:00)
                    # A1 is treated as not crossing midnight despite its time values
                    if shift['shift_type'] == 'A1':
                        logger.info(f"Preserving A1 shift on same day: {shift}")
                    else:
                        # For other shifts that might cross midnight, add a day
                        logger.info(f"Adjusting overnight shift: {shift}")
                        end += timedelta(days=1)
                
                shift['start'] = start.strftime('%Y-%m-%d %H:%M')
                shift['end'] = end.strftime('%Y-%m-%d %H:%M')
                logger.info(f"Saved shift times: {shift['start']} to {shift['end']}")
                
            except (ValueError, TypeError) as e:
                logger.error(f"Invalid shift times: {shift}")
                raise ValueError(f"Invalid shift times: {str(e)}")

        # Ensure data directory exists
        os.makedirs(os.path.dirname(SHIFTS_FILE), exist_ok=True)
        
        with open(SHIFTS_FILE, 'w') as f:
            json.dump(shifts, f, indent=2)
        logger.info("Successfully saved shifts to file")
    except Exception as e:
        logger.error(f"Error saving shifts: {str(e)}", exc_info=True)
        raise

def load_templates():
    if os.path.exists(TEMPLATES_FILE):
        with open(TEMPLATES_FILE, 'r') as f:
            return json.load(f)
    return []

def save_templates(templates):
    with open(TEMPLATES_FILE, 'w') as f:
        json.dump(templates, f, indent=2)

def load_note_templates():
    if os.path.exists(NOTE_TEMPLATES_FILE):
        with open(NOTE_TEMPLATES_FILE, 'r') as f:
            templates = json.load(f)
            # Ensure default template exists
            if not any(t['id'] == 'default' for t in templates):
                templates.append(DEFAULT_NOTE_TEMPLATE)
            return templates
    return [DEFAULT_NOTE_TEMPLATE]

def save_note_templates(templates):
    with open(NOTE_TEMPLATES_FILE, 'w') as f:
        json.dump(templates, f, indent=2)

def calculate_hours(shifts, caregiver_id):
    total_hours = 0
    for shift in shifts:
        if shift['caregiver_id'] == caregiver_id:
            start = parser.parse(shift['start'])
            end = parser.parse(shift['end'])
            duration = end - start
            total_hours += duration.total_seconds() / 3600
    return total_hours

def calculate_shift_times(date_str, shift_type):
    shift_def = SHIFT_DEFINITIONS[shift_type]
    start_time = datetime.strptime(f"{date_str} {shift_def['start']}", "%Y-%m-%d %H:%M")
    end_time = datetime.strptime(f"{date_str} {shift_def['end']}", "%Y-%m-%d %H:%M")
    
    # Handle shifts that cross midnight
    if end_time <= start_time:
        end_time += timedelta(days=1)
    
    return start_time, end_time

def init_data():
    try:
        # Initialize with sample data if files don't exist
        if not os.path.exists(CAREGIVERS_FILE):
            sample_caregivers = [
                {'id': i, 'name': f'Caregiver {i}', 'max_hours': 40, 'color': f'#{"".join([hex(i*30)[2:].zfill(2) for _ in range(3)])}'}
                for i in range(1, 8)
            ]
            save_caregivers(sample_caregivers)
            logger.info("Sample caregivers data created")

        if not os.path.exists(SHIFTS_FILE):
            save_shifts([])
            logger.info("Shifts file created")

        if not os.path.exists(TEMPLATES_FILE):
            save_templates([])
            logger.info("Templates file created")
            
        if not os.path.exists(NOTE_TEMPLATES_FILE):
            save_note_templates([DEFAULT_NOTE_TEMPLATE])
            logger.info("Note templates created")
            
        if not os.path.exists(AUDIT_EVENTS_FILE):
            save_audit_events([])
            logger.info("Audit events file created")
            
        if not os.path.exists(WEEK_STATES_FILE):
            save_week_states({})
            logger.info("Week states file created")

    except Exception as e:
        logger.error(f"Error initializing data: {str(e)}")
        raise

# Routes
@app.route('/')
def index():
    try:
        return render_template('index.html')
    except Exception as e:
        logger.error(f"Error in index route: {str(e)}")
        return "An error occurred", 500

@app.route('/schedule')
def schedule():
    try:
        caregivers = load_caregivers()
        shifts = load_shifts()
        templates = load_templates()
        logger.info(f"Retrieved {len(caregivers)} caregivers and {len(shifts)} shifts")
        return render_template('schedule.html', 
                             shifts=shifts, 
                             caregivers=caregivers,
                             templates=templates,
                             shift_definitions=SHIFT_DEFINITIONS)
    except Exception as e:
        logger.error(f"Error in schedule route: {str(e)}")
        return "An error occurred while loading the schedule", 500

@app.route('/api/templates', methods=['POST'])
def save_template():
    try:
        template_data = request.json
        logger.info(f"Received template data: {json.dumps(template_data, indent=2)}")
        
        templates = load_templates()
        
        if 'name' not in template_data or 'shifts' not in template_data:
            return jsonify({'error': 'Missing required fields'}), 400
        
        # Load caregivers for enriching shift data
        caregivers = {str(c['id']): c for c in load_caregivers()}
        
        # Validate and enrich shift data
        for shift in template_data['shifts']:
            required_fields = ['day', 'caregiver_id', 'shift_type']
            if not all(field in shift for field in required_fields):
                missing = [f for f in required_fields if f not in shift]
                return jsonify({'error': f'Missing required fields in shift: {", ".join(missing)}'}), 400
            
            # Validate shift type exists
            if shift['shift_type'] not in SHIFT_DEFINITIONS:
                return jsonify({'error': f'Invalid shift type: {shift["shift_type"]}. Valid types are: {", ".join(SHIFT_DEFINITIONS.keys())}'}), 400
            
            # Add caregiver details to shift
            caregiver = caregivers.get(str(shift['caregiver_id']))
            if caregiver:
                shift['caregiver_name'] = caregiver['name']
                shift['color'] = caregiver['color']
            else:
                return jsonify({'error': f'Caregiver not found: {shift["caregiver_id"]}'}), 400
        
        # Check for duplicate template names
        existing_template = next((t for t in templates if t['name'].lower() == template_data['name'].lower()), None)
        if existing_template:
            # Update existing template instead of creating a new one
            existing_template['shifts'] = template_data['shifts']
            save_templates(templates)
            logger.info(f"Updated existing template: {json.dumps(existing_template, indent=2)}")
            return jsonify(existing_template)
            
        # Create new template with unique ID
        max_id = max([int(t['id']) for t in templates]) if templates else 0
        template_data['id'] = str(max_id + 1)
        templates.append(template_data)
        save_templates(templates)
        logger.info(f"Saved new template: {json.dumps(template_data, indent=2)}")
        return jsonify(template_data)
    except Exception as e:
        logger.error(f"Error in save_template: {str(e)}")
        return jsonify({'error': 'An error occurred while saving template'}), 500

@app.route('/api/templates', methods=['GET'])
def get_templates():
    try:
        templates = load_templates()
        # Sort templates by ID to ensure consistent ordering
        templates.sort(key=lambda x: int(x['id']))
        return jsonify(templates)
    except Exception as e:
        logger.error(f"Error in get_templates: {str(e)}")
        return jsonify({'error': 'An error occurred while fetching templates'}), 500

@app.route('/api/templates/<template_id>', methods=['DELETE'])
def delete_template(template_id):
    try:
        templates = load_templates()
        templates = [t for t in templates if t['id'] != template_id]
        save_templates(templates)
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error in delete_template: {str(e)}")
        return jsonify({'error': 'An error occurred while deleting template'}), 500

@app.route('/api/templates/<int:template_id>', methods=['GET'])
def get_template(template_id):
    try:
        templates = load_templates()
        template = next((t for t in templates if int(t['id']) == template_id), None)
        if not template:
            return jsonify({'error': 'Template not found'}), 404
            
        # Add caregiver details to template shifts
        caregivers = {str(c['id']): c for c in load_caregivers()}
        for shift in template['shifts']:
            caregiver = caregivers.get(str(shift['caregiver_id']))
            if caregiver:
                shift['caregiver_name'] = caregiver['name']
                shift['color'] = caregiver['color']
                
        return jsonify(template)
    except Exception as e:
        logger.error(f"Error getting template {template_id}: {str(e)}")
        return jsonify({'error': 'Failed to get template'}), 500

@app.route('/api/caregivers', methods=['GET'])
def get_caregivers():
    try:
        caregivers = load_caregivers()
        return jsonify(caregivers)
    except Exception as e:
        logger.error(f"Error in get_caregivers: {str(e)}")
        return jsonify({'error': 'An error occurred while fetching caregivers'}), 500

@app.route('/api/caregivers', methods=['POST'])
def add_caregiver():
    try:
        caregiver_data = request.json
        
        # Validate required fields
        if not all(field in caregiver_data for field in ['name', 'max_hours', 'color']):
            return jsonify({'error': 'Missing required fields'}), 400
            
        # Validate max_hours
        max_hours = int(caregiver_data['max_hours'])
        if max_hours <= 0 or max_hours > 168:
            return jsonify({'error': 'Maximum hours must be between 1 and 168'}), 400
            
        caregivers = load_caregivers()
        
        # Generate new ID
        new_id = max([c['id'] for c in caregivers]) + 1 if caregivers else 1
        
        new_caregiver = {
            'id': new_id,
            'name': caregiver_data['name'].strip(),
            'max_hours': max_hours,
            'color': caregiver_data['color']
        }
        
        caregivers.append(new_caregiver)
        save_caregivers(caregivers)
        
        return jsonify(new_caregiver)
    except Exception as e:
        logger.error(f"Error in add_caregiver: {str(e)}")
        return jsonify({'error': 'An error occurred while adding caregiver'}), 500

@app.route('/api/caregivers/<int:caregiver_id>', methods=['PUT'])
def update_caregiver(caregiver_id):
    try:
        caregiver_data = request.json
        
        # Validate required fields
        if not all(field in caregiver_data for field in ['name', 'max_hours', 'color']):
            return jsonify({'error': 'Missing required fields'}), 400
            
        # Validate max_hours
        max_hours = int(caregiver_data['max_hours'])
        if max_hours <= 0 or max_hours > 168:
            return jsonify({'error': 'Maximum hours must be between 1 and 168'}), 400
            
        caregivers = load_caregivers()
        caregiver_index = next((i for i, c in enumerate(caregivers) if c['id'] == caregiver_id), None)
        
        if caregiver_index is None:
            return jsonify({'error': 'Caregiver not found'}), 404
            
        caregivers[caregiver_index].update({
            'name': caregiver_data['name'].strip(),
            'max_hours': max_hours,
            'color': caregiver_data['color']
        })
        
        save_caregivers(caregivers)
        return jsonify(caregivers[caregiver_index])
    except Exception as e:
        logger.error(f"Error in update_caregiver: {str(e)}")
        return jsonify({'error': 'An error occurred while updating caregiver'}), 500

@app.route('/api/caregivers/<int:caregiver_id>', methods=['DELETE'])
def delete_caregiver(caregiver_id):
    try:
        caregivers = load_caregivers()
        shifts = load_shifts()
        templates = load_templates()
        
        # Remove caregiver from list
        caregivers = [c for c in caregivers if c['id'] != caregiver_id]
        save_caregivers(caregivers)
        
        # Remove caregiver's shifts
        shifts = [s for s in shifts if int(s['caregiver_id']) != caregiver_id]
        save_shifts(shifts)
        
        # Remove caregiver from templates
        for template in templates:
            template['shifts'] = [s for s in template['shifts'] if int(s['caregiver_id']) != caregiver_id]
        save_templates(templates)
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error in delete_caregiver: {str(e)}")
        return jsonify({'error': 'An error occurred while deleting caregiver'}), 500

@app.route('/weekly')
def weekly():
    try:
        templates = load_templates()
        caregivers = load_caregivers()
        last_template = load_last_template()
        return render_template('weekly.html', 
                             templates=templates,
                             caregivers=caregivers,
                             shift_definitions=SHIFT_DEFINITIONS,
                             last_template=last_template)
    except Exception as e:
        logger.error(f"Error in weekly route: {str(e)}")
        return "An error occurred", 500

@app.route('/weekly_viewer')
def weekly_viewer():
    try:
        templates = load_templates()
        caregivers = load_caregivers()
        return render_template('weekly_viewer.html', 
                             templates=templates,
                             caregivers=caregivers,
                             shift_definitions=SHIFT_DEFINITIONS)
    except Exception as e:
        logger.error(f"Error in weekly_viewer route: {str(e)}")
        return "An error occurred", 500

@app.route('/weekly_views')
def weekly_views():
    try:
        caregivers = load_caregivers()
        return render_template('weekly_views.html', 
                             caregivers=caregivers,
                             shift_definitions=SHIFT_DEFINITIONS)
    except Exception as e:
        logger.error(f"Error in weekly_views route: {str(e)}")
        return "An error occurred", 500

@app.route('/api/shifts', methods=['GET'])
def get_shifts():
    start_date = request.args.get('start')
    end_date = request.args.get('end')
    days = request.args.get('days')
    
    if days:
        # If days specified, calculate end_date from start_date + days
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end_date = (start + timedelta(days=int(days)-1)).strftime('%Y-%m-%d')
    
    if not start_date or not end_date:
        return jsonify({'error': 'Missing date range parameters'}), 400
    
    try:
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        end = end.replace(hour=23, minute=59, second=59)
        
        logger.info(f"Loading shifts from {start} to {end}")
        
        shifts = load_shifts()
        filtered_shifts = []
        
        caregivers = {str(c['id']): c for c in load_caregivers()}
        
        for shift in shifts:
            shift_start = parser.parse(shift['start'])
            shift_end = parser.parse(shift['end'])
            
            # Calculate if this shift should be shown in the date range
            # Special handling for A1 (overnight) shifts:
            # Include an A1 shift if its start date is between start and end
            is_a1_shift = shift['shift_type'] == 'A1'
            
            # For A1 shifts, always use the start date to determine inclusion
            # For other shifts, use standard date range check
            if is_a1_shift:
                logger.info(f"Processing A1 shift: {shift}")
                shift_date = shift_start.date()
                is_in_range = start.date() <= shift_date <= end.date()
                
                if is_in_range:
                    logger.info(f"Including A1 shift based on start date: {shift_date}")
            else:
                is_in_range = start <= shift_start <= end
            
            if is_in_range:
                # Add caregiver details
                caregiver = caregivers.get(str(shift['caregiver_id']))
                if caregiver:
                    shift['caregiver_name'] = caregiver['name']
                    shift['color'] = caregiver['color']
                filtered_shifts.append(shift)
        
        logger.info(f"Returning {len(filtered_shifts)} shifts")
        return jsonify(filtered_shifts)
    except ValueError:
        return jsonify({'error': 'Invalid date format'}), 400

@app.route('/api/shifts', methods=['DELETE'])
def delete_shifts():
    try:
        start_date = request.args.get('start')
        end_date = request.args.get('end')
        
        if not start_date or not end_date:
            return jsonify({'error': 'Missing date range parameters'}), 400
            
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        end = end.replace(hour=23, minute=59, second=59)
        
        shifts = load_shifts()
        remaining_shifts = []
        
        for shift in shifts:
            shift_start = parser.parse(shift['start'])
            if not (start <= shift_start <= end):
                remaining_shifts.append(shift)
        
        save_shifts(remaining_shifts)
        return jsonify({'success': True})
    except ValueError:
        return jsonify({'error': 'Invalid date format'}), 400
    except Exception as e:
        logger.error(f"Error deleting shifts: {str(e)}")
        return jsonify({'error': 'An error occurred while deleting shifts'}), 500

@app.route('/api/templates/<int:template_id>/apply', methods=['POST'])
def apply_template(template_id):
    try:
        data = request.json
        if not data or 'start_date' not in data:
            return jsonify({'error': 'Start date is required'}), 400
            
        start_date = data['start_date']
        num_weeks = int(data.get('num_weeks', 1))
        
        if num_weeks < 1 or num_weeks > 12:
            return jsonify({'error': 'Number of weeks must be between 1 and 12'}), 400
            
        # Load template
        templates = load_templates()
        template = next((t for t in templates if int(t['id']) == template_id), None)
        if not template:
            return jsonify({'error': 'Template not found'}), 404
            
        # Convert start_date to datetime
        week_start = datetime.strptime(start_date, '%Y-%m-%d')
        
        # Load existing shifts
        shifts = load_shifts()
        
        # Calculate end date
        end_date = week_start + timedelta(weeks=num_weeks)
        
        # Remove existing shifts in the date range
        shifts = [s for s in shifts if not (
            week_start <= parser.parse(s['start']) <= end_date
        )]
        
        # Generate new shifts from template
        new_shifts = []
        max_id = max([int(s['id']) for s in shifts]) if shifts else 0
        shift_id = max_id + 1
        
        for week in range(num_weeks):
            current_week_start = week_start + timedelta(weeks=week)
            
            for template_shift in template['shifts']:
                # Get the day number (0 = Monday, 6 = Sunday)
                template_day = normalize_day_value(template_shift['day'])
                
                # Calculate the date for this shift
                shift_date = current_week_start + timedelta(days=template_day)
                
                # Get shift times from definitions
                shift_def = SHIFT_DEFINITIONS[template_shift['shift_type']]
                
                # Create shift start and end times
                shift_start = datetime.strptime(f"{shift_date.date()} {shift_def['start']}", "%Y-%m-%d %H:%M")
                shift_end = datetime.strptime(f"{shift_date.date()} {shift_def['end']}", "%Y-%m-%d %H:%M")
                
                # Handle shifts that cross midnight
                if shift_def['end'] <= shift_def['start']:
                    shift_end += timedelta(days=1)
                
                # Create new shift
                new_shift = {
                    'id': str(shift_id),
                    'caregiver_id': template_shift['caregiver_id'],
                    'shift_type': template_shift['shift_type'],
                    'start': shift_start.strftime('%Y-%m-%d %H:%M'),
                    'end': shift_end.strftime('%Y-%m-%d %H:%M')
                }
                
                new_shifts.append(new_shift)
                shift_id += 1
        
        # Add new shifts to existing ones
        shifts.extend(new_shifts)
        
        # Save updated shifts
        save_shifts(shifts)
        
        # Create audit event
        create_audit_event(
            AUDIT_EVENT_TYPES['TEMPLATE_APPLIED'],
            details={
                'template_id': template_id,
                'template_name': template['name'],
                'start_date': start_date,
                'num_weeks': num_weeks,
                'shifts_added': len(new_shifts)
            }
        )
        
        return jsonify({'message': f'Template applied successfully for {num_weeks} weeks'})
        
    except ValueError as e:
        logger.error(f"Value error in apply_template: {str(e)}")
        return jsonify({'error': 'Invalid date format or template data'}), 400
    except Exception as e:
        logger.error(f"Error applying template: {str(e)}", exc_info=True)
        return jsonify({'error': 'An error occurred while applying the template'}), 500

def load_week_states():
    if os.path.exists(WEEK_STATES_FILE):
        with open(WEEK_STATES_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_week_states(states):
    with open(WEEK_STATES_FILE, 'w') as f:
        json.dump(states, f, indent=2)

def load_last_template():
    if os.path.exists(LAST_TEMPLATE_FILE):
        with open(LAST_TEMPLATE_FILE, 'r') as f:
            return json.load(f)
    return None

def save_last_template(template_info):
    with open(LAST_TEMPLATE_FILE, 'w') as f:
        json.dump(template_info, f, indent=2)

@app.route('/api/week-state', methods=['GET'])
def get_week_state():
    try:
        week_start = request.args.get('week_start')
        if not week_start:
            return jsonify({'error': 'Week start date is required'}), 400
            
        # Validate date format
        try:
            datetime.strptime(week_start, '%Y-%m-%d')
        except ValueError:
            return jsonify({'error': 'Invalid date format'}), 400
            
        states = load_week_states()
        return jsonify({
            'week_state': states.get(week_start, {}),
            'last_template': load_last_template()
        })
    except Exception as e:
        logger.error(f"Error getting week state: {str(e)}")
        return jsonify({'error': 'Failed to get week state'}), 500

@app.route('/api/week-state', methods=['POST'])
def save_week_state():
    try:
        data = request.json
        if not data or 'week_start' not in data:
            return jsonify({'error': 'Week start date is required'}), 400
            
        # Validate date format
        try:
            datetime.strptime(data['week_start'], '%Y-%m-%d')
        except ValueError:
            return jsonify({'error': 'Invalid date format'}), 400
            
        # Validate shifts data
        if 'shifts' in data and not isinstance(data['shifts'], list):
            return jsonify({'error': 'Shifts must be an array'}), 400
            
        states = load_week_states()
        states[data['week_start']] = {
            'shifts': data.get('shifts', []),
            'template': data.get('template')
        }
        save_week_states(states)
        
        # Save last template if provided
        if data.get('template'):
            save_last_template(data['template'])
            
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error saving week state: {str(e)}")
        return jsonify({'error': 'Failed to save week state'}), 500

@app.route('/api/week-state', methods=['DELETE'])
def clear_week_state():
    try:
        week_start = request.args.get('week_start')
        if not week_start:
            return jsonify({'error': 'Week start date is required'}), 400
            
        # Validate date format
        try:
            datetime.strptime(week_start, '%Y-%m-%d')
        except ValueError:
            return jsonify({'error': 'Invalid date format'}), 400
            
        states = load_week_states()
        if week_start in states:
            del states[week_start]
            save_week_states(states)
            
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error clearing week state: {str(e)}")
        return jsonify({'error': 'Failed to clear week state'}), 500

@app.route('/api/shifts/<shift_id>', methods=['GET'])
def get_shift(shift_id):
    try:
        # Load existing shifts
        shifts = load_shifts()
        
        # Convert shift_id to string for comparison
        shift_id_str = str(shift_id)
        
        # Find the shift
        shift = next((s for s in shifts if str(s.get('id')) == shift_id_str), None)
        
        if shift is None:
            return jsonify({'error': 'Shift not found'}), 404
            
        # Add caregiver details
        caregiver = next((c for c in load_caregivers() if str(c['id']) == str(shift['caregiver_id'])), None)
        if caregiver:
            shift['caregiver_name'] = caregiver['name']
            shift['color'] = caregiver['color']
            
        return jsonify(shift)
        
    except Exception as e:
        logger.error(f"Error getting shift {shift_id}: {str(e)}")
        return jsonify({'error': 'Failed to get shift'}), 500

@app.route('/api/shifts/<shift_id>', methods=['PUT'])
def update_shift(shift_id):
    try:
        shift_data = request.json
        logger.info(f"Updating shift {shift_id} with data: {shift_data}")
        
        # Validate required fields
        required_fields = ['caregiver_id', 'shift_type', 'start', 'end']
        if not all(field in shift_data for field in required_fields):
            missing = [f for f in required_fields if f not in shift_data]
            return jsonify({'error': f'Missing required fields: {", ".join(missing)}'}), 400
            
        # Validate shift type
        if shift_data['shift_type'] not in SHIFT_DEFINITIONS:
            return jsonify({'error': f'Invalid shift type: {shift_data["shift_type"]}'}), 400
            
        # Load existing shifts
        shifts = load_shifts()
        
        # Convert shift_id to string for comparison
        shift_id_str = str(shift_id)
        
        # Find the shift to update
        shift_index = next((i for i, shift in enumerate(shifts) if str(shift['id']) == shift_id_str), None)
        
        if shift_index is None:
            return jsonify({'error': 'Shift not found'}), 404
        
        # Store old shift for audit log
        old_shift = dict(shifts[shift_index])
            
        # Get caregiver
        caregivers = load_caregivers()
        caregiver = next((c for c in caregivers if str(c['id']) == str(shift_data['caregiver_id'])), None)
        if not caregiver:
            return jsonify({'error': f'Caregiver not found: {shift_data["caregiver_id"]}'}), 400
            
        # Parse and validate dates
        try:
            start_time = parser.parse(shift_data['start'])
            end_time = parser.parse(shift_data['end'])
            
            # Format times consistently
            shift_data['start'] = start_time.strftime('%Y-%m-%d %H:%M')
            
            # Apply the same overnight logic as in add_shift
            start_date = start_time.date()
            end_date = end_time.date()
            
            # Only adjust if end date is actually before start date
            if end_date < start_date:
                logger.warning(f"End date {end_date} is before start date {start_date} - adjusting")
                end_time += timedelta(days=1)
            # For same-day shifts, check if we need to adjust for overnight
            elif end_date == start_date and end_time <= start_time:
                # Special handling for A1 shift - it should not cross midnight
                if shift_data['shift_type'] == 'A1':
                    logger.info(f"Preserving A1 shift on same day: {shift_data}")
                else:
                    # For other shifts that truly cross midnight, add a day to end time
                    logger.info(f"Adjusting overnight shift: {shift_data}")
                    end_time += timedelta(days=1)
            
            shift_data['end'] = end_time.strftime('%Y-%m-%d %H:%M')
            
        except ValueError as e:
            return jsonify({'error': f'Invalid date format: {str(e)}'}), 400
            
        # Update shift
        shifts[shift_index] = {
            'id': shift_id_str,
            'caregiver_id': str(shift_data['caregiver_id']),
            'shift_type': shift_data['shift_type'],
            'start': shift_data['start'],
            'end': shift_data['end']
        }
        
        # Add caregiver details for response
        shifts[shift_index]['caregiver_name'] = caregiver['name']
        shifts[shift_index]['color'] = caregiver['color']
        
        # Save updated shifts
        save_shifts(shifts)
        logger.info(f"Successfully updated shift: {shifts[shift_index]}")
        
        # Create audit event
        create_audit_event(
            AUDIT_EVENT_TYPES['SHIFT_MODIFIED'],
            details={
                'shift_id': shift_id_str,
                'old_shift': old_shift,
                'new_shift': shifts[shift_index]
            }
        )
        
        return jsonify(shifts[shift_index])
        
    except Exception as e:
        logger.error(f"Error updating shift {shift_id}: {str(e)}", exc_info=True)
        return jsonify({'error': f'Failed to update shift: {str(e)}'}), 500

@app.route('/api/shifts/<shift_id>', methods=['DELETE'])
def delete_shift(shift_id):
    try:
        # Load existing shifts
        shifts = load_shifts()
        
        # Convert shift_id to string for comparison
        shift_id_str = str(shift_id)
        
        # Find the shift to delete
        shift_index = next((i for i, shift in enumerate(shifts) if str(shift.get('id')) == shift_id_str), None)
        
        if shift_index is None:
            return jsonify({'error': 'Shift not found'}), 404
            
        # Remove the shift
        deleted_shift = shifts.pop(shift_index)
        
        # Save updated shifts
        save_shifts(shifts)
        
        # Create audit event
        create_audit_event(
            AUDIT_EVENT_TYPES['SHIFT_DELETED'],
            details={
                'shift_id': shift_id_str,
                'shift_type': deleted_shift['shift_type'],
                'caregiver_id': deleted_shift['caregiver_id'],
                'start': deleted_shift['start'],
                'end': deleted_shift['end']
            }
        )
        
        return jsonify({'message': 'Shift deleted successfully', 'shift': deleted_shift})
        
    except Exception as e:
        app.logger.error(f"Error deleting shift {shift_id}: {str(e)}")
        return jsonify({'error': 'Failed to delete shift'}), 500

@app.route('/api/shifts/download-ics', methods=['GET'])
def download_ics():
    try:
        start_date = request.args.get('start')
        end_date = request.args.get('end')
        
        if not start_date or not end_date:
            return jsonify({'error': 'Missing date range parameters'}), 400
            
        # Create calendar
        cal = Calendar()
        cal.add('prodid', '-//Caregiver Scheduler//EN')
        cal.add('version', '2.0')
        cal.add('calscale', 'GREGORIAN')
        cal.add('method', 'PUBLISH')
        
        # Get shifts for the date range
        shifts = load_shifts()
        caregivers = {str(c['id']): c for c in load_caregivers()}
        
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        end = end.replace(hour=23, minute=59, second=59)
        
        # Filter shifts and create events
        for shift in shifts:
            shift_start = parser.parse(shift['start'])
            if start <= shift_start <= end:
                event = Event()
                
                # Get caregiver details
                caregiver = caregivers.get(str(shift['caregiver_id']))
                caregiver_name = caregiver['name'] if caregiver else 'Unknown Caregiver'
                
                # Set event properties
                event.add('summary', f"{caregiver_name} - {shift['shift_type']} Shift")
                event.add('dtstart', shift_start)
                event.add('dtend', parser.parse(shift['end']))
                event.add('dtstamp', datetime.now(pytz.UTC))
                event.add('uid', f"{shift['id']}@caregiverscheduler")
                
                if caregiver:
                    event.add('description', f"Caregiver: {caregiver_name}\nShift Type: {shift['shift_type']}")
                    event.add('categories', ['Caregiver Shift'])
                    
                cal.add_component(event)
        
        # Generate ICS file content
        ics_content = cal.to_ical()
        
        # Create response with ICS file
        response = app.make_response(ics_content)
        response.headers['Content-Type'] = 'text/calendar'
        response.headers['Content-Disposition'] = 'attachment; filename=schedule.ics'
        
        return response
        
    except Exception as e:
        logger.error(f"Error generating ICS file: {str(e)}")
        return jsonify({'error': 'Failed to generate ICS file'}), 500

@app.route('/api/shifts', methods=['POST'])
def add_shift():
    try:
        shift_data = request.json
        logger.info(f"Received shift data: {shift_data}")
        
        # Validate required fields
        required_fields = ['caregiver_id', 'shift_type', 'start', 'end']
        if not all(field in shift_data for field in required_fields):
            missing = [f for f in required_fields if f not in shift_data]
            return jsonify({'error': f'Missing required fields: {", ".join(missing)}'}), 400
            
        # Validate shift type
        if shift_data['shift_type'] not in SHIFT_DEFINITIONS:
            return jsonify({'error': f'Invalid shift type: {shift_data["shift_type"]}'}), 400
            
        # Find caregiver by ID (not by name)
        caregivers = load_caregivers()
        caregiver = next((c for c in caregivers if str(c['id']) == str(shift_data['caregiver_id'])), None)
        if not caregiver:
            return jsonify({'error': f'Caregiver not found with ID: {shift_data["caregiver_id"]}'}), 400
            
        # Parse and validate dates
        try:
            start_time = parser.parse(shift_data['start'])
            end_time = parser.parse(shift_data['end'])
            
            # Format times consistently
            shift_data['start'] = start_time.strftime('%Y-%m-%d %H:%M')
            
            # CRITICAL FIX: Use the same rules as save_shifts
            # Only adjust dates if they're different AND the end time is before the start time
            start_date = start_time.date()
            end_date = end_time.date()
            
            # Log original dates
            logger.info(f"Original dates for shift {shift_data['shift_type']}: {start_date} to {end_date}")
            
            # Only adjust if end date is actually before start date
            if end_date < start_date:
                logger.warning(f"End date {end_date} is before start date {start_date} - adjusting")
                end_time += timedelta(days=1)
            # For same-day shifts, check if we need to adjust for overnight
            elif end_date == start_date and end_time <= start_time:
                # Special handling for A1 shift - it should not cross midnight
                if shift_data['shift_type'] == 'A1':
                    logger.info(f"Preserving A1 shift on same day: {shift_data}")
                else:
                    # For other shifts that truly cross midnight, add a day to end time
                    logger.info(f"Adjusting overnight shift: {shift_data}")
                    end_time += timedelta(days=1)
            
            shift_data['end'] = end_time.strftime('%Y-%m-%d %H:%M')
            logger.info(f"Final shift times: {shift_data['start']} to {shift_data['end']}")
            
        except ValueError as e:
            return jsonify({'error': f'Invalid date format: {str(e)}'}), 400
            
        # Load existing shifts
        shifts = load_shifts()
        
        # Generate new ID
        new_id = str(max([int(s['id']) for s in shifts]) + 1) if shifts else '1'
        
        # Create new shift
        new_shift = {
            'id': new_id,
            'caregiver_id': str(caregiver['id']),
            'shift_type': shift_data['shift_type'],
            'start': shift_data['start'],
            'end': shift_data['end']
        }
        
        # Add caregiver details for response
        new_shift['caregiver_name'] = caregiver['name']
        new_shift['color'] = caregiver['color']
        
        # Add to shifts list
        shifts.append(new_shift)
        
        # Save updated shifts - will go through save_shifts with same logic
        save_shifts(shifts)
        logger.info(f"Successfully saved shift: {new_shift}")
        
        # Create audit event
        create_audit_event(
            AUDIT_EVENT_TYPES['SHIFT_ADDED'],
            details={
                'shift_id': new_id,
                'shift_type': new_shift['shift_type'],
                'caregiver_id': new_shift['caregiver_id'],
                'caregiver_name': caregiver['name'],
                'start': new_shift['start'],
                'end': new_shift['end']
            }
        )
        
        return jsonify(new_shift), 201
        
    except Exception as e:
        logger.error(f"Error adding shift: {str(e)}", exc_info=True)
        return jsonify({'error': f'Failed to add shift: {str(e)}'}), 500

@app.route('/monthly')
def monthly():
    try:
        caregivers = load_caregivers()
        return render_template('monthly.html', 
                             caregivers=caregivers,
                             shift_definitions=SHIFT_DEFINITIONS)
    except Exception as e:
        logger.error(f"Error in monthly route: {str(e)}")
        return "An error occurred", 500

@app.route('/hourly')
def hourly():
    try:
        caregivers = load_caregivers()
        templates = load_templates()
        return render_template('hourly.html', 
                             caregivers=caregivers,
                             templates=templates,
                             shift_definitions=SHIFT_DEFINITIONS)
    except Exception as e:
        logger.error(f"Error in hourly route: {str(e)}")
        return "An error occurred", 500

@app.route('/calendar')
def calendar():
    try:
        caregivers = load_caregivers()
        templates = load_templates()
        
        return render_template('calendar.html', 
                             caregivers=caregivers,
                             templates=templates,
                             shift_definitions=SHIFT_DEFINITIONS)
    except Exception as e:
        logger.error(f"Error in calendar route: {str(e)}")
        return "An error occurred", 500

@app.route('/api/audit-events', methods=['GET'])
def get_audit_events():
    try:
        start_date = request.args.get('start')
        end_date = request.args.get('end')
        event_type = request.args.get('type')
        
        events = load_audit_events()
        filtered_events = []
        
        # Apply filters if provided
        for event in events:
            # Check date range if provided
            if start_date or end_date:
                event_date = datetime.strptime(event['timestamp'], '%Y-%m-%d %H:%M:%S')
                
                if start_date:
                    start = datetime.strptime(start_date, '%Y-%m-%d')
                    if event_date < start:
                        continue
                        
                if end_date:
                    end = datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
                    if event_date > end:
                        continue
            
            # Check event type if provided
            if event_type and event['type'] != event_type:
                continue
                
            filtered_events.append(event)
        
        # Sort by timestamp descending (newest first)
        filtered_events.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return jsonify(filtered_events)
    except Exception as e:
        logger.error(f"Error getting audit events: {str(e)}")
        return jsonify({'error': 'Failed to get audit events'}), 500

@app.route('/audit')
def audit_view():
    try:
        return render_template('audit.html', event_types=AUDIT_EVENT_TYPES)
    except Exception as e:
        logger.error(f"Error in audit route: {str(e)}")
        return "An error occurred", 500

if __name__ == '__main__':
    init_data()
    app.run(debug=True, host='0.0.0.0') 