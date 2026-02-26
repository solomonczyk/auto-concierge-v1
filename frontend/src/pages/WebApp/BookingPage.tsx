import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { format, isSameDay, startOfDay, startOfMonth, endOfMonth, startOfWeek, endOfWeek, eachDayOfInterval, isSameMonth, addMonths, subMonths, addDays } from 'date-fns';
import { ru } from 'date-fns/locale';
import { Calendar as CalendarIcon, Clock, ChevronLeft, CheckCircle2, Car } from 'lucide-react';

declare global {
    interface Window {
        Telegram: any;
    }
}

interface Service {
    id: number;
    name: string;
    duration_minutes: number;
    base_price: number;
}

const CalendarModal = ({
    isOpen,
    onClose,
    selectedDate,
    onSelect
}: {
    isOpen: boolean,
    onClose: () => void,
    selectedDate: Date,
    onSelect: (date: Date) => void
}) => {
    const [currentMonth, setCurrentMonth] = useState(startOfMonth(selectedDate));

    if (!isOpen) return null;

    const monthStart = startOfMonth(currentMonth);
    const monthEnd = endOfMonth(monthStart);
    const startDate = startOfWeek(monthStart, { weekStartsOn: 1 });
    const endDate = endOfWeek(monthEnd, { weekStartsOn: 1 });

    const calendarDays = eachDayOfInterval({
        start: startDate,
        end: endDate,
    });

    const weekDays = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
            <div className="bg-background w-full max-w-sm rounded-3xl shadow-2xl overflow-hidden border border-border animate-in zoom-in-95 duration-200">
                <div className="p-4 bg-primary/5 border-b border-border flex items-center justify-between">
                    <button onClick={() => setCurrentMonth(subMonths(currentMonth, 1))} className="p-2 hover:bg-accent rounded-full transition-colors">
                        <ChevronLeft className="w-5 h-5" />
                    </button>
                    <div className="font-bold text-lg capitalize">
                        {format(currentMonth, 'LLLL yyyy', { locale: ru })}
                    </div>
                    <button onClick={() => setCurrentMonth(addMonths(currentMonth, 1))} className="p-2 hover:bg-accent rounded-full transition-colors rotate-180">
                        <ChevronLeft className="w-5 h-5" />
                    </button>
                </div>

                <div className="p-4">
                    <div className="grid grid-cols-7 mb-2">
                        {weekDays.map(day => (
                            <div key={day} className="text-center text-[10px] font-bold opacity-40 uppercase">
                                {day}
                            </div>
                        ))}
                    </div>
                    <div className="grid grid-cols-7 gap-1">
                        {calendarDays.map(day => {
                            const isSelected = isSameDay(day, selectedDate);
                            const isCurrentMonth = isSameMonth(day, monthStart);
                            const now = new Date();
                            const isPast = startOfDay(day) < startOfDay(now);

                            // Inactivate today if past working hours (18:00)
                            const isToday = isSameDay(day, now);
                            const isWorkDayEnded = now.getHours() >= 18;
                            const isTodayDisabled = isToday && isWorkDayEnded;

                            const isTooFar = startOfDay(day) > addDays(startOfDay(now), 30);

                            return (
                                <button
                                    key={day.toISOString()}
                                    disabled={isPast || isTooFar || isTodayDisabled}
                                    onClick={() => {
                                        onSelect(day);
                                        onClose();
                                    }}
                                    className={`
                                        h-10 w-full rounded-xl flex items-center justify-center text-sm font-medium transition-all
                                        ${isSelected ? 'bg-primary text-primary-foreground shadow-lg shadow-primary/30 scale-110 z-10' : ''}
                                        ${!isSelected && isCurrentMonth ? 'hover:bg-accent' : ''}
                                        ${!isCurrentMonth ? 'opacity-20' : ''}
                                        ${(isPast || isTooFar || isTodayDisabled) && !isSelected ? 'opacity-10 cursor-not-allowed grayscale' : ''}
                                    `}
                                >
                                    {format(day, 'd')}
                                </button>
                            );
                        })}
                    </div>
                </div>

                <div className="p-4 bg-accent/20 flex gap-3">
                    <Button variant="ghost" className="flex-1 rounded-xl font-bold" onClick={onClose}>
                        ОТМЕНА
                    </Button>
                </div>
            </div>
        </div>
    );
};

// ── Car info step (inserted between service pick and date/time pick) ──────────
function CarInfoStep({
    carMake, setCarMake,
    carYear, setCarYear,
    vin, setVin,
    onBack, onNext,
}: {
    carMake: string; setCarMake: (v: string) => void;
    carYear: string; setCarYear: (v: string) => void;
    vin: string; setVin: (v: string) => void;
    onBack: () => void;
    onNext: () => void;
}) {
    const yearNum = parseInt(carYear);
    const yearValid = !carYear || (yearNum >= 1970 && yearNum <= new Date().getFullYear() + 1);
    const vinValid = !vin || (vin.length === 17 && /^[A-HJ-NPR-Z0-9]{17}$/i.test(vin));
    const canContinue = carMake.trim().length >= 2;

    return (
        <div className="p-4 bg-background min-h-screen text-foreground space-y-5 animate-in fade-in duration-500">
            <div className="flex items-center gap-2 mb-2">
                <Button variant="ghost" size="icon" onClick={onBack} className="-ml-2">
                    <ChevronLeft className="w-6 h-6" />
                </Button>
                <h1 className="text-xl font-bold">Данные автомобиля</h1>
            </div>

            <p className="text-sm text-muted-foreground">
                Укажите информацию о вашем автомобиле. Это поможет мастеру подготовиться.
            </p>

            {/* Марка и модель */}
            <div className="space-y-1.5">
                <label className="text-xs font-bold uppercase opacity-60 flex items-center gap-1">
                    <Car className="w-3.5 h-3.5" /> Марка и модель <span className="text-red-400">*</span>
                </label>
                <input
                    type="text"
                    placeholder="Например: Toyota Camry"
                    value={carMake}
                    onChange={e => setCarMake(e.target.value)}
                    className="w-full bg-accent/40 border border-border rounded-xl px-4 py-3 text-base outline-none focus:border-primary transition-colors placeholder:opacity-40"
                />
            </div>

            {/* Год выпуска */}
            <div className="space-y-1.5">
                <label className="text-xs font-bold uppercase opacity-60">Год выпуска</label>
                <input
                    type="number"
                    placeholder="Например: 2019"
                    value={carYear}
                    onChange={e => setCarYear(e.target.value)}
                    min={1970}
                    max={new Date().getFullYear() + 1}
                    className={`w-full bg-accent/40 border rounded-xl px-4 py-3 text-base outline-none focus:border-primary transition-colors placeholder:opacity-40 ${yearValid ? 'border-border' : 'border-red-400'
                        }`}
                />
                {!yearValid && <p className="text-xs text-red-400">Введите корректный год (1970–{new Date().getFullYear() + 1})</p>}
            </div>

            {/* VIN */}
            <div className="space-y-1.5">
                <label className="text-xs font-bold uppercase opacity-60">VIN-номер</label>
                <input
                    type="text"
                    placeholder="17 символов, например: XTA21120053926700"
                    value={vin}
                    onChange={e => setVin(e.target.value.toUpperCase())}
                    maxLength={17}
                    className={`w-full bg-accent/40 border rounded-xl px-4 py-3 text-base font-mono outline-none focus:border-primary transition-colors placeholder:opacity-40 placeholder:font-sans ${vinValid ? 'border-border' : 'border-red-400'
                        }`}
                />
                <div className="flex justify-between">
                    {!vinValid && <p className="text-xs text-red-400">VIN должен содержать ровно 17 символов (A-Z, 0-9, без I, O, Q)</p>}
                    <p className="text-xs opacity-40 ml-auto">{vin.length}/17</p>
                </div>
            </div>

            <div className="pt-4">
                <Button
                    className="w-full h-14 text-lg font-bold shadow-xl shadow-primary/20"
                    disabled={!canContinue || !yearValid || !vinValid}
                    onClick={onNext}
                >
                    ДАЛЕЕ → ВЫБРАТЬ ДАТУ И ВРЕМЯ
                </Button>
            </div>
        </div>
    );
}

export default function BookingPage() {
    const [services, setServices] = useState<Service[]>([]);
    const [loading, setLoading] = useState(true);
    const [selectedService, setSelectedService] = useState<Service | null>(null);
    // Step: 'service' | 'car' | 'datetime'
    const [step, setStep] = useState<'service' | 'car' | 'datetime'>('service');
    // Car info
    const [carMake, setCarMake] = useState('');
    const [carYear, setCarYear] = useState('');
    const [vin, setVin] = useState('');
    const [selectedDate, setSelectedDate] = useState<Date>(() => {
        const now = new Date();
        if (now.getHours() >= 18) {
            return startOfDay(addDays(now, 1));
        }
        return startOfDay(now);
    });
    const [availableSlots, setAvailableSlots] = useState<string[]>([]);
    const [selectedTime, setSelectedTime] = useState<string>('');
    const [slotsLoading, setSlotsLoading] = useState(false);
    const [showCalendar, setShowCalendar] = useState(false);

    // Auto-scroll horizontal dates list when selectedDate changes
    useEffect(() => {
        const dateId = `date-${format(selectedDate, 'yyyy-MM-dd')}`;
        const element = document.getElementById(dateId);
        if (element) {
            element.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
        }
    }, [selectedDate]);

    // Detect if we are in edit mode
    const urlParams = new URLSearchParams(window.location.search);
    const appointmentId = urlParams.get('appointment_id');
    const isEditMode = !!appointmentId;

    const tg = window.Telegram?.WebApp;

    useEffect(() => {
        tg?.ready();
        tg?.expand();

        // Set Telegram WebApp theme to match dark premium dashboard
        tg?.setHeaderColor('#0a1628');       // --background
        tg?.setBackgroundColor('#0a1628');   // --background

        tg?.MainButton.setParams({
            text: isEditMode ? '✏️ ПЕРЕНЕСТИ ЗАПИСЬ' : '✅ ПОДТВЕРДИТЬ',
            color: '#3b82f6',                // --primary (electric blue)
            text_color: '#0f172a',           // --primary-foreground (dark)
        });

        const fetchData = async () => {
            try {
                const servicesRes = await api.get('/services/');
                setServices(servicesRes.data);

                if (appointmentId) {
                    try {
                        const apptRes = await api.get(`/appointments/${appointmentId}`);
                        const appt = apptRes.data;
                        const service = servicesRes.data.find((s: Service) => s.id === appt.service_id);

                        if (service) {
                            setSelectedService(service);
                            // Pre-select date from appointment
                            const apptDate = new Date(appt.start_time);
                            setSelectedDate(startOfDay(apptDate));
                        }
                    } catch (apptErr) {
                        console.error("Failed to fetch appointment", apptErr);
                    }
                }
            } catch (err) {
                console.error("Failed to fetch data", err);
            } finally {
                setLoading(false);
            }
        };

        fetchData();
    }, [isEditMode, appointmentId]);


    // Next 30 days range computed inline where needed

    // Fetch slots when service or date changes
    useEffect(() => {
        if (selectedService && selectedDate) {
            setSlotsLoading(true);
            setSelectedTime('');
            const dateStr = format(selectedDate, 'yyyy-MM-dd');

            api.get('/slots/available', {
                params: {
                    shop_id: 1, // Default for MVP
                    service_duration: selectedService.duration_minutes,
                    target_date: dateStr
                }
            })
                .then(res => setAvailableSlots(res.data))
                .catch(err => {
                    console.error("Failed to fetch slots", err);
                    setAvailableSlots([]);
                })
                .finally(() => setSlotsLoading(false));
        }
    }, [selectedService, selectedDate]);

    const handleSubmit = (isWaitlist: boolean = false) => {
        if (!selectedService || (!selectedTime && !isWaitlist)) return;

        const data = {
            service_id: selectedService.id,
            date: isWaitlist ? format(selectedDate, 'yyyy-MM-dd') : selectedTime,
            appointment_id: appointmentId,
            is_waitlist: isWaitlist,
            // Vehicle info
            car_make: carMake.trim() || null,
            car_year: carYear ? parseInt(carYear) : null,
            vin: vin.trim() || null,
        };

        if (tg) {
            tg.sendData(JSON.stringify(data));
        } else {
            console.log("WebApp Data would be sent:", data);
            alert(isWaitlist ? "Заявка в лист ожидания отправлена!" : (isEditMode ? "Запись изменена!" : "Запись создана!"));
        }
    };

    useEffect(() => {
        if (selectedService && selectedTime) {
            tg?.MainButton.show();
            tg?.MainButton.onClick(() => handleSubmit(false));
        } else {
            tg?.MainButton.hide();
        }
        return () => {
            tg?.MainButton.offClick(() => handleSubmit(false));
        }
    }, [selectedService, selectedTime]);

    const handleClose = () => {
        tg?.close();
    };

    // --- Car info step ---
    if (selectedService && step === 'car') {
        return (
            <CarInfoStep
                carMake={carMake} setCarMake={setCarMake}
                carYear={carYear} setCarYear={setCarYear}
                vin={vin} setVin={setVin}
                onBack={() => { setStep('service'); setSelectedService(null); }}
                onNext={() => setStep('datetime')}
            />
        );
    }

    // --- Date / Time step ---
    if (selectedService && step === 'datetime') {
        return (
            <div className="p-4 bg-background min-h-screen text-foreground space-y-6 animate-in fade-in duration-500">
                <div className="flex items-center gap-2 mb-2">
                    <Button variant="ghost" size="icon" onClick={() => setStep('car')} className="-ml-2">
                        <ChevronLeft className="w-6 h-6" />
                    </Button>
                    <h1 className="text-xl font-bold">Детали записи</h1>
                </div>

                {/* Service Summary Card */}
                <div className="bg-primary/5 p-4 rounded-xl border border-primary/20 flex justify-between items-center transition-all">
                    <div>
                        <div className="font-bold text-lg">{selectedService.name}</div>
                        <div className="text-muted-foreground text-sm">{selectedService.duration_minutes} мин • {selectedService.base_price} ₽</div>
                    </div>
                    <CheckCircle2 className="text-primary w-6 h-6 opacity-20" />
                </div>

                {/* Date Selection */}
                <div className="space-y-3">
                    <div className="flex items-center justify-between text-sm font-semibold opacity-70">
                        <div className="flex items-center gap-2">
                            <CalendarIcon className="w-4 h-4" />
                            ВЫБЕРИТЕ ДАТУ
                        </div>

                        <Button
                            variant="outline"
                            size="sm"
                            className="h-9 px-3 text-primary border-primary/20 bg-primary/5 hover:bg-primary/10 gap-2 font-bold"
                            onClick={() => setShowCalendar(true)}
                        >
                            <CalendarIcon className="w-4 h-4" />
                            ОТКРЫТЬ КАЛЕНДАРЬ
                        </Button>
                    </div>

                    {/* Selected Date Display - Replaces the horizontal scroller */}
                    <div className="bg-accent/30 p-4 rounded-xl flex items-center justify-between animate-in slide-in-from-top-2 duration-300">
                        <div className="flex items-center gap-3">
                            <div className="bg-primary/10 p-2.5 rounded-xl">
                                <CalendarIcon className="text-primary w-5 h-5" />
                            </div>
                            <div>
                                <div className="font-bold text-base capitalize">
                                    {format(selectedDate, 'd MMMM yyyy', { locale: ru })}
                                </div>
                                <div className="text-muted-foreground text-xs uppercase font-bold opacity-60 flex items-center gap-1.5">
                                    <div className="w-1 h-1 rounded-full bg-primary" />
                                    {format(selectedDate, 'EEEE', { locale: ru })}
                                </div>
                            </div>
                        </div>
                        <Button variant="ghost" size="sm" className="text-primary font-bold pr-0" onClick={() => setShowCalendar(true)}>
                            ИЗМЕНИТЬ
                        </Button>
                    </div>
                </div>

                <CalendarModal
                    isOpen={showCalendar}
                    onClose={() => setShowCalendar(false)}
                    selectedDate={selectedDate}
                    onSelect={(date) => {
                        setSelectedDate(date);
                    }}
                />


                {/* Time Selection */}
                <div className="space-y-3">
                    <div className="flex items-center gap-2 text-sm font-semibold opacity-70">
                        <Clock className="w-4 h-4" />
                        ВЫБЕРИТЕ ВРЕМЯ
                    </div>

                    {slotsLoading ? (
                        <div className="grid grid-cols-4 gap-2">
                            {[1, 2, 3, 4, 5, 6, 7, 8].map(i => (
                                <div key={i} className="h-10 bg-accent/20 animate-pulse rounded-lg" />
                            ))}
                        </div>
                    ) : availableSlots.length > 0 ? (
                        <div className="grid grid-cols-4 gap-2">
                            {availableSlots.map((slot) => {
                                const isSelected = selectedTime === slot;
                                const timeLabel = format(new Date(slot), 'HH:mm');
                                return (
                                    <button
                                        key={slot}
                                        onClick={() => setSelectedTime(slot)}
                                        className={`h-10 rounded-lg flex items-center justify-center text-sm font-medium transition-all ${isSelected
                                            ? 'bg-primary text-primary-foreground shadow-md'
                                            : 'bg-accent/40 hover:bg-accent'
                                            }`}
                                    >
                                        {timeLabel}
                                    </button>
                                );
                            })}
                        </div>
                    ) : (
                        <div className="text-center py-6 bg-accent/10 rounded-xl border border-dashed border-accent space-y-3">
                            <p className="text-muted-foreground text-sm">Нет свободных слотов на эту дату</p>
                            <Button
                                variant="outline"
                                size="sm"
                                className="font-bold border-primary text-primary hover:bg-primary/10"
                                onClick={() => handleSubmit(true)}
                            >
                                ОСТАВИТЬ ЗАЯВКУ В ЛИСТ ОЖИДАНИЯ
                            </Button>
                        </div>
                    )}
                </div>

                <div className="pt-4">
                    <Button
                        className="w-full h-14 text-lg font-bold shadow-xl shadow-primary/20"
                        disabled={!selectedTime}
                        onClick={() => handleSubmit(false)}
                    >
                        ПОДТВЕРДИТЬ ЗАПИСЬ
                    </Button>
                </div>
            </div>
        )
    }

    return (
        <div className="p-4 max-w-md mx-auto min-h-screen bg-background text-foreground animate-in fade-in duration-500">
            <h1 className="text-2xl font-black mb-6 tracking-tight">ВЫБЕРИТЕ УСЛУГУ</h1>

            <div className="space-y-4">
                {services.map(service => (
                    <Card
                        key={service.id}
                        className="overflow-hidden border-none bg-accent/30 hover:bg-accent/50 transition-all active:scale-[0.98] cursor-pointer"
                        onClick={() => { setSelectedService(service); setStep('car'); }}
                    >
                        <CardHeader className="p-4 pb-1">
                            <CardTitle className="text-lg flex justify-between items-start">
                                <span className="font-bold">
                                    {service.name.charAt(0).toUpperCase() + service.name.slice(1)}
                                </span>
                                <span className="text-primary font-black">{service.base_price} ₽</span>
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="p-4 pt-0">
                            <div className="flex items-center gap-1.5 text-muted-foreground text-sm">
                                <Clock className="w-3.5 h-3.5" />
                                {service.duration_minutes} мин.
                            </div>
                        </CardContent>
                    </Card>
                ))}
            </div>

            {loading && (
                <div className="space-y-4 pt-4">
                    {[1, 2, 3].map(i => (
                        <div key={i} className="h-24 bg-accent/20 animate-pulse rounded-xl" />
                    ))}
                </div>
            )}

            {!loading && services.length === 0 && (
                <div className="text-center py-20 opacity-50">
                    Услуги не найдены.
                </div>
            )}

            <div className="mt-12 text-center">
                <Button variant="ghost" size="sm" onClick={handleClose} className="opacity-50 hover:opacity-100">Закрыть</Button>
            </div>
        </div>
    );
}
