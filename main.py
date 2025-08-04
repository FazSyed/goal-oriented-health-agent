import asyncio
import agents.main_controller as mc

def main():
    """
    Main entry point for the elderly dehydration monitoring system.
    This system uses multiple agents to:
    1. Monitor patient vitals (SensorAgent)
    2. Analyze health data and predict dehydration risk (HealthAgent)  
    3. Send appropriate reminders or alerts (ReminderAgent/AlertAgent)
    """
    print("Starting Elderly Dehydration Monitoring System...")
    
    try:
        asyncio.run(mc.main())
    except KeyboardInterrupt:
        print("\n⚠️  System interrupted by user")
    except Exception as e:
        print(f"❌ System error: {e}")
    finally:
        print("👋 Goodbye!")

if __name__ == "__main__":
    main()