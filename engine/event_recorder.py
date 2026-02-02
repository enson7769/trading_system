from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import json
import os
import concurrent.futures
from utils.logger import logger
from config.config import config

class EventRecorder:
    def __init__(self, 
                 data_dir: str = None,
                 max_workers: int = None,
                 batch_size: int = None):
        """Initialize event recorder with performance optimizations"""
        # Load configuration
        events_config = config.get_events_config()
        
        # Use provided value or config value or default
        if data_dir is None:
            data_dir = events_config.get('data_dir', 'data/events')
        if max_workers is None:
            max_workers = events_config.get('max_workers', 4)
        if batch_size is None:
            batch_size = events_config.get('batch_size', 10)
        
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)
        self.important_events = events_config.get('important_events', [
            'powell_speech',
            'unemployment_rate',
            'cpi',
            'ppi',
            'fomc_meeting',
            'gdp',
            'retail_sales',
            'nonfarm_payrolls'
        ])
        self.max_workers = max_workers
        self.batch_size = batch_size
        self._event_index: Dict[str, List[str]] = {}
        self._build_index()
    
    def _build_index(self) -> None:
        """Build in-memory index for faster event lookup"""
        try:
            for event_name in self.important_events:
                self._event_index[event_name] = []
            
            for filename in os.listdir(self.data_dir):
                if filename.endswith('.json'):
                    try:
                        event_name = filename.split('_')[0]
                        if event_name in self.important_events:
                            self._event_index[event_name].append(filename)
                    except Exception:
                        pass
            
            # Sort files by timestamp for each event
            for event_name in self._event_index:
                self._event_index[event_name].sort()
                
        except Exception as e:
            logger.error(f"Error building event index: {e}")
    
    def record_event_data(self, event_name: str, timestamp: datetime, data: Dict) -> bool:
        """Record event data with error handling and index update"""
        try:
            if event_name not in self.important_events:
                logger.warning(f"Event {event_name} not in important events list")
            
            filename = f"{event_name}_{timestamp.strftime('%Y%m%d_%H%M%S')}.json"
            filepath = os.path.join(self.data_dir, filename)
            
            event_data = {
                'event_name': event_name,
                'timestamp': timestamp.isoformat(),
                'data': data,
                'recorded_at': datetime.now().isoformat()
            }
            
            # Write with error handling
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(event_data, f, indent=2, ensure_ascii=False)
            
            # Update index
            if event_name not in self._event_index:
                self._event_index[event_name] = []
            self._event_index[event_name].append(filename)
            self._event_index[event_name].sort()
            
            logger.info(f"Recorded event data for {event_name} at {timestamp}")
            return True
            
        except Exception as e:
            logger.error(f"Error recording event data: {e}")
            return False
    
    def record_events_batch(self, events: List[Tuple[str, datetime, Dict]]) -> Dict[str, Any]:
        """Record multiple events in batch for improved performance"""
        results = {
            'total': len(events),
            'success': 0,
            'failed': 0,
            'errors': []
        }
        
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {
                    executor.submit(self.record_event_data, event_name, timestamp, data): i
                    for i, (event_name, timestamp, data) in enumerate(events)
                }
                
                for future in concurrent.futures.as_completed(futures):
                    try:
                        success = future.result()
                        if success:
                            results['success'] += 1
                        else:
                            results['failed'] += 1
                    except Exception as e:
                        results['failed'] += 1
                        results['errors'].append(str(e))
        
        except Exception as e:
            logger.error(f"Error in batch recording: {e}")
            results['errors'].append(str(e))
        
        return results
    
    def analyze_event_impact(self, event_name: str, lookback_minutes: int = 30) -> Optional[Dict[str, Any]]:
        """Analyze event impact with cached lookups"""
        try:
            # Use index for faster lookup
            if event_name not in self._event_index or not self._event_index[event_name]:
                return None
            
            latest_event = self._event_index[event_name][-1]
            filepath = os.path.join(self.data_dir, latest_event)
            
            with open(filepath, 'r', encoding='utf-8') as f:
                event_data = json.load(f)
            
            event_time = datetime.fromisoformat(event_data['timestamp'])
            analysis_window_start = event_time - timedelta(minutes=lookback_minutes)
            analysis_window_end = event_time + timedelta(minutes=lookback_minutes)
            
            return {
                'event_name': event_name,
                'event_time': event_time,
                'analysis_window': {
                    'start': analysis_window_start.isoformat(),
                    'end': analysis_window_end.isoformat()
                },
                'event_data': event_data['data'],
                'analysis_time': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error analyzing event impact: {e}")
            return None
    
    def get_recent_events(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get recent events with parallel processing for better performance"""
        recent_events = []
        cutoff_time = datetime.now() - timedelta(days=days)
        
        try:
            # Collect all relevant files first
            relevant_files = []
            for event_name, files in self._event_index.items():
                for filename in files:
                    # Extract timestamp from filename
                    try:
                        timestamp_str = '_'.join(filename.split('_')[1:]).replace('.json', '')
                        file_time = datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S')
                        if file_time >= cutoff_time:
                            relevant_files.append((event_name, filename))
                    except Exception:
                        pass
            
            # Process files in parallel
            def process_file(file_info: Tuple[str, str]) -> Optional[Dict[str, Any]]:
                event_name, filename = file_info
                filepath = os.path.join(self.data_dir, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        return json.load(f)
                except Exception as e:
                    logger.error(f"Error reading event file {filename}: {e}")
                    return None
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                results = executor.map(process_file, relevant_files)
                
                for result in results:
                    if result:
                        recent_events.append(result)
            
            # Sort by timestamp
            recent_events.sort(key=lambda x: x['timestamp'], reverse=True)
            
        except Exception as e:
            logger.error(f"Error getting recent events: {e}")
        
        return recent_events
    
    def get_event_statistics(self) -> Dict[str, Any]:
        """Get statistics about recorded events"""
        try:
            stats = {
                'total_events': 0,
                'events_by_type': {},
                'total_size': 0,
                'last_updated': datetime.now().isoformat()
            }
            
            for event_name, files in self._event_index.items():
                count = len(files)
                stats['total_events'] += count
                stats['events_by_type'][event_name] = count
                
                # Estimate total size
                for filename in files:
                    filepath = os.path.join(self.data_dir, filename)
                    try:
                        stats['total_size'] += os.path.getsize(filepath)
                    except Exception:
                        pass
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting event statistics: {e}")
            return {
                'total_events': 0,
                'events_by_type': {},
                'total_size': 0,
                'last_updated': datetime.now().isoformat(),
                'error': str(e)
            }

