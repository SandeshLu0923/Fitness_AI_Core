#!/usr/bin/env python3
"""
Backend Verification Script
Checks MongoDB connectivity, Groq authentication, and FastAPI health.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
from motor.motor_asyncio import AsyncIOMotorClient
from groq import Groq
from app.config import GROQ_API_KEY, GROQ_MODEL, MONGODB_URL, HOST, PORT


async def verify_mongodb():
    """Verify MongoDB connection."""
    print("\n[1/4] Testing MongoDB Connection...")
    try:
        client = AsyncIOMotorClient(MONGODB_URL, serverSelectionTimeoutMS=5000)
        await client.admin.command('ping')
        print("    ✅ MongoDB connection successful")
        print(f"    📍 Connected to: {MONGODB_URL.split('@')[1] if '@' in MONGODB_URL else MONGODB_URL}")
        return True
    except Exception as e:
        print(f"    ❌ MongoDB connection failed: {e}")
        print(f"    💡 Check: Is MongoDB running? Is MONGODB_URL correct?")
        return False


def verify_groq():
    """Verify Groq API authentication."""
    print("\n[2/4] Testing Groq API Authentication...")
    try:
        client = Groq(api_key=GROQ_API_KEY)
        
        # Make minimal API call to verify auth
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=10
        )
        
        if response.choices and response.choices[0].message.content:
            print("    ✅ Groq API authentication successful")
            print(f"    📍 Model: {GROQ_MODEL}")
            print(f"    📍 Usage: {response.usage.input_tokens} input tokens, {response.usage.output_tokens} output tokens")
            return True
    except Exception as e:
        print(f"    ❌ Groq API authentication failed: {e}")
        print(f"    💡 Check: Is GROQ_API_KEY valid? Is Groq service up?")
        return False


async def verify_fastapi():
    """Verify FastAPI server health."""
    print("\n[3/4] Testing FastAPI Health Endpoint...")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"http://{HOST}:{PORT}/health",
                timeout=5.0
            )
            
            if response.status_code == 200:
                print("    ✅ FastAPI server is healthy")
                print(f"    📍 Response: {response.json()}")
                return True
            else:
                print(f"    ⚠️  Unexpected status code: {response.status_code}")
                return False
    except httpx.ConnectError:
        print(f"    ❌ Cannot connect to FastAPI server at {HOST}:{PORT}")
        print(f"    💡 Check: Is FastAPI running? Is HOST/PORT correct?")
        return False
    except Exception as e:
        print(f"    ❌ Health check failed: {e}")
        return False


async def verify_openapi_schema():
    """Verify OpenAPI schema is available."""
    print("\n[4/4] Testing OpenAPI Schema...")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"http://{HOST}:{PORT}/openapi.json",
                timeout=5.0
            )
            
            if response.status_code == 200:
                schema = response.json()
                paths = schema.get("paths", {})
                print(f"    ✅ OpenAPI schema available")
                print(f"    📍 Total endpoints: {len(paths)}")
                
                # List endpoints by tag
                endpoint_count = 0
                for path in paths:
                    for method in paths[path]:
                        endpoint_count += 1
                print(f"    📍 Total methods: {endpoint_count}")
                return True
            else:
                print(f"    ❌ OpenAPI schema unavailable (status: {response.status_code})")
                return False
    except Exception as e:
        print(f"    ❌ OpenAPI schema test failed: {e}")
        return False


async def main():
    """Run all verification tests."""
    print("╔═══════════════════════════════════════════╗")
    print("║   BACKEND VERIFICATION SUITE              ║")
    print("║   AI Gym Assistant - System Health Check  ║")
    print("╚═══════════════════════════════════════════╝")
    
    results = {}
    
    # Test 1: MongoDB
    results['mongodb'] = await verify_mongodb()
    
    # Test 2: Groq
    results['groq'] = verify_groq()
    
    # Test 3: FastAPI
    results['fastapi'] = await verify_fastapi()
    
    # Test 4: OpenAPI Schema
    results['openapi'] = await verify_openapi_schema()
    
    # Summary
    print("\n" + "="*50)
    print("VERIFICATION SUMMARY")
    print("="*50)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test.upper():.<30} {status}")
    
    print("="*50)
    print(f"\nResult: {passed}/{total} checks passed")
    
    if passed == total:
        print("\n🎉 All systems GO! Backend is ready for testing.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} check(s) failed. Review issues above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
