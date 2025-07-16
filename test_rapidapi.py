#!/usr/bin/env python3
"""
Test script to validate RapidAPI Champions League integration
"""

import os
import sys
import json
import requests
from datetime import datetime

def test_rapidapi_endpoints():
    """Test all RapidAPI endpoints"""
    
    # Configuration
    base_url = "https://uefa-champions-league1.p.rapidapi.com"
    headers = {
        'X-RapidAPI-Key': '7da786eaa7msha6089bc5228b539p1d2750jsnb29f032c2590',
        'X-RapidAPI-Host': 'uefa-champions-league1.p.rapidapi.com'
    }
    
    # Test endpoints
    endpoints = [
        {
            'name': 'Standings',
            'endpoint': '/standingsv2',
            'params': {'season': '2024'}
        },
        {
            'name': 'Team Info',
            'endpoint': '/team/info',
            'params': {'teamId': '83'}
        },
        {
            'name': 'Team Performance',
            'endpoint': '/team/perfomance',
            'params': {'teamId': '83'}
        },
        {
            'name': 'Team Results',
            'endpoint': '/team/results',
            'params': {'teamId': '83', 'season': '2024'}
        },
        {
            'name': 'Athlete Statistics',
            'endpoint': '/athlete/statistic',
            'params': {'playerId': '150225'}
        },
        {
            'name': 'Athlete Bio',
            'endpoint': '/athlete/bio',
            'params': {'playerId': '150225'}
        },
        {
            'name': 'Athlete Season Stats',
            'endpoint': '/athlete/season',
            'params': {'playerId': '150225'}
        },
        {
            'name': 'Athlete Overview',
            'endpoint': '/athlete/overview',
            'params': {'playerId': '150225'}
        }
    ]
    
    results = []
    
    for test in endpoints:
        print(f"Testing {test['name']}...")
        
        try:
            url = f"{base_url}{test['endpoint']}"
            response = requests.get(url, headers=headers, params=test['params'], timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                result = {
                    'endpoint': test['name'],
                    'status': 'SUCCESS',
                    'status_code': response.status_code,
                    'data_size': len(json.dumps(data)),
                    'response_time': response.elapsed.total_seconds(),
                    'sample_keys': list(data.keys()) if isinstance(data, dict) else []
                }
                print(f"  ✓ SUCCESS - {result['data_size']} bytes in {result['response_time']:.2f}s")
                
            else:
                result = {
                    'endpoint': test['name'],
                    'status': 'FAILED',
                    'status_code': response.status_code,
                    'error': response.text,
                    'response_time': response.elapsed.total_seconds()
                }
                print(f"  ✗ FAILED - {response.status_code}: {response.text}")
                
        except Exception as e:
            result = {
                'endpoint': test['name'],
                'status': 'ERROR',
                'error': str(e)
            }
            print(f"  ✗ ERROR - {str(e)}")
            
        results.append(result)
        
    return results

def test_ingestion_service():
    """Test the ingestion service locally"""
    
    print("\nTesting Ingestion Service...")
    
    # Test health endpoint
    try:
        response = requests.get('http://localhost:8080/health', timeout=5)
        if response.status_code == 200:
            print("  ✓ Health check passed")
        else:
            print(f"  ✗ Health check failed: {response.status_code}")
    except Exception as e:
        print(f"  ✗ Health check error: {str(e)}")
    
    # Test endpoints list
    try:
        response = requests.get('http://localhost:8080/endpoints', timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"  ✓ Available endpoints: {len(data.get('endpoints', []))}")
        else:
            print(f"  ✗ Endpoints list failed: {response.status_code}")
    except Exception as e:
        print(f"  ✗ Endpoints list error: {str(e)}")
    
    # Test ingestion
    try:
        payload = {
            "endpoint": "standings",
            "season": "2024"
        }
        response = requests.post(
            'http://localhost:8080/ingest',
            json=payload,
            timeout=30
        )
        if response.status_code == 200:
            print("  ✓ Ingestion test passed")
        else:
            print(f"  ✗ Ingestion test failed: {response.status_code}")
    except Exception as e:
        print(f"  ✗ Ingestion test error: {str(e)}")

def generate_test_report(results):
    """Generate a test report"""
    
    print("\n" + "="*60)
    print("RAPIDAPI TEST REPORT")
    print("="*60)
    
    success_count = sum(1 for r in results if r['status'] == 'SUCCESS')
    total_count = len(results)
    
    print(f"Total Tests: {total_count}")
    print(f"Successful: {success_count}")
    print(f"Failed: {total_count - success_count}")
    print(f"Success Rate: {(success_count/total_count)*100:.1f}%")
    
    print("\nDetailed Results:")
    for result in results:
        status_icon = "✓" if result['status'] == 'SUCCESS' else "✗"
        print(f"  {status_icon} {result['endpoint']}: {result['status']}")
        if 'response_time' in result:
            print(f"    Response Time: {result['response_time']:.2f}s")
        if 'data_size' in result:
            print(f"    Data Size: {result['data_size']} bytes")
    
    # Save detailed report
    report_file = f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\nDetailed report saved to: {report_file}")

if __name__ == "__main__":
    print("Champions League RapidAPI Integration Test")
    print("=" * 50)
    
    # Test RapidAPI endpoints
    results = test_rapidapi_endpoints()
    
    # Test ingestion service (optional)
    if len(sys.argv) > 1 and sys.argv[1] == "--test-service":
        test_ingestion_service()
    
    # Generate report
    generate_test_report(results)
    
    # Exit with appropriate code
    success_count = sum(1 for r in results if r['status'] == 'SUCCESS')
    if success_count == len(results):
        print("\n🎉 All tests passed!")
        sys.exit(0)
    else:
        print(f"\n⚠️  {len(results) - success_count} tests failed")
        sys.exit(1)
