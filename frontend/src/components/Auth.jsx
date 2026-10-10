import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import {
    FiUser, FiLock, FiMail, FiCheckCircle, FiShield,
    FiTruck, FiPhone, FiCreditCard, FiList,
    FiBriefcase, FiKey, FiAlertTriangle, FiEye, FiEyeOff,
    FiFileText
} from 'react-icons/fi';

import { API_BASE_URL as API_URL } from '../utils/constants';
import { ROLE_OPTIONS, LOGIN_PAGE_CONFIG } from '../utils/authConfig';
import { ROLE_ROUTES } from '../context/AuthContext';

const Auth = ({ setAuth }) => {
    const [isLogin, setIsLogin] = useState(true);
    const [role, setRole] = useState('rider');

    const [showPassword, setShowPassword] = useState(false);
    const [showConfirmPassword, setShowConfirmPassword] = useState(false);
    const [rememberMe, setRememberMe] = useState(false);
    const [formData, setFormData] = useState({
        username: '',
        password: '',
        confirmPassword: '',
        full_name: '',
        phone: '',
        email: '',
        admin_code: '',
        license_number: '',
        vehicle_type: 'motorcycle',
        vehicle_number: '',
        gender: 'female',
        emergency_contact_phone: '',
        emergency_contact_email: ''
    });
    const [errors, setErrors] = useState({});
    const [globalError, setGlobalError] = useState('');
    const [loading, setLoading] = useState(false);
    const navigate = useNavigate();

    // Check if registration is allowed for current role
    const canRegister = LOGIN_PAGE_CONFIG.allowRegistration[role];

    // Filter visible roles for selection
    const visibleRoles = ROLE_OPTIONS.filter(r =>
        LOGIN_PAGE_CONFIG.visibleRoles.includes(r.value)
    );

    // Sync isLogin with canRegister when role changes
    useEffect(() => {
        if (!canRegister && !isLogin) {
            setIsLogin(true);
        }
    }, [role, canRegister, isLogin]);

    // Real-time validation
    useEffect(() => {
        if (!isLogin) {
            validateField('email', formData.email);
            validateField('password', formData.password);
            if (formData.confirmPassword) {
                validateField('confirmPassword', formData.confirmPassword);
            }
        }
    }, [formData.email, formData.password, formData.confirmPassword, isLogin]);

    const validateField = (name, value) => {
        let newErrors = { ...errors };

        switch (name) {
            case 'email':
                if (value && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
                    newErrors.email = 'Invalid email format';
                } else {
                    delete newErrors.email;
                }
                break;
            case 'password':
                if (!isLogin && value && value.length < 6) {
                    newErrors.password = 'Password must be at least 6 characters';
                } else {
                    delete newErrors.password;
                }
                break;
            case 'confirmPassword':
                if (value && value !== formData.password) {
                    newErrors.confirmPassword = 'Passwords do not match';
                } else {
                    delete newErrors.confirmPassword;
                }
                break;
            case 'phone':
                if (value && !/^\+?[\d\s-()]+$/.test(value)) {
                    newErrors.phone = 'Invalid phone number';
                } else {
                    delete newErrors.phone;
                }
                break;
            default:
                break;
        }

        setErrors(newErrors);
    };

    const handleInputChange = (e) => {
        const { name, value } = e.target;
        setFormData({
            ...formData,
            [name]: value
        });
        validateField(name, value);
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        setGlobalError('');

        // Validate all fields
        if (!isLogin && formData.password !== formData.confirmPassword) {
            setGlobalError('Passwords do not match');
            setLoading(false);
            return;
        }

        if (Object.keys(errors).length > 0) {
            setGlobalError('Please fix all errors before submitting');
            setLoading(false);
            return;
        }

        try {
            const endpoint = isLogin ? '/auth/login' : '/auth/register';

            const payload = isLogin
                ? {
                    username: formData.email,
                    password: formData.password,
                    role: role // Pass role to login for backend validation
                }
                : {
                    ...formData,
                    username: formData.email,
                    role: role
                };

            const response = await axios.post(`${API_URL}${endpoint}`, payload);

            if (isLogin) {
                const loginData = {
                    access_token: response.data.access_token,
                    username: response.data.username,
                    role: response.data.role,
                    user_id: response.data.user_id,
                    full_name: response.data.full_name,
                    email: response.data.email,
                };
                setAuth(loginData);

                // Navigate to role-specific dashboard
                const roleRoute = ROLE_ROUTES[response.data.role] || '/rider/dashboard';
                navigate(roleRoute);
            } else {
                setIsLogin(true);
                setGlobalError('Success! Please sign in with your new credentials.');
            }
        } catch (err) {
            setGlobalError(err.response?.data?.detail || 'Authentication failed. Check your network or credentials.');
        } finally {
            setLoading(false);
        }
    };


    return (
        <div className="min-h-screen flex items-center justify-center bg-slate-50 px-4 py-12 relative overflow-hidden">
            {/* Background Decorative Elements */}
            <div className="absolute top-0 left-0 w-full h-full overflow-hidden z-0 pointer-events-none">
                <div className="absolute top-[-10%] left-[-5%] w-[400px] h-[400px] bg-indigo-500/5 rounded-full blur-[120px]"></div>
                <div className="absolute bottom-[-10%] right-[-5%] w-[400px] h-[400px] bg-blue-500/5 rounded-full blur-[120px]"></div>
            </div>

            <div className="max-w-2xl w-full z-10 transition-all transform duration-500">


                {/* Header */}
                <div className="text-center mb-8">
                    <div className="inline-flex items-center justify-center p-4 bg-white rounded-3xl mb-5 shadow-[0_20px_50px_rgba(8,112,184,0.1)] relative group border border-slate-100">
                        <FiShield size={40} className="text-indigo-600 relative z-10" />
                    </div>
                    <h1 className="text-5xl font-black text-slate-900 mb-2 tracking-tight">
                        SmartShield
                    </h1>
                    <p className="text-slate-400 text-xs font-bold tracking-[0.2em] uppercase">AI-Powered Multi-Role Trust Route</p>
                </div>

                <div className="bg-white border border-slate-200 p-1 rounded-[2.5rem] shadow-[0_32px_64px_-16px_rgba(0,0,0,0.08)] overflow-hidden">
                    <div className="p-8 md:p-10">
                        {/* Role Tabs */}
                        <div className="flex flex-wrap justify-center gap-2 mb-10">
                            {visibleRoles.map((option) => {
                                const Icon = option.icon;
                                const isSelected = role === option.value;
                                return (
                                    <button
                                        key={option.value}
                                        type="button"
                                        onClick={() => setRole(option.value)}
                                        className={`flex items-center gap-2 px-5 py-2.5 rounded-full border transition-all duration-300 ${isSelected
                                            ? 'bg-indigo-600 border-indigo-600 text-white shadow-lg shadow-indigo-600/20'
                                            : 'border-slate-100 text-slate-400 hover:border-slate-200 hover:text-slate-600 bg-slate-50'
                                            }`}
                                    >
                                        <Icon size={18} />
                                        <span className="font-bold text-xs tracking-wide">{option.label}</span>
                                    </button>
                                );
                            })}
                        </div>

                        {/* Login/Signup Toggle */}
                        <div className="flex bg-slate-100 p-1 rounded-2xl mb-8 border border-slate-200 max-w-sm mx-auto">
                            <button
                                onClick={() => setIsLogin(true)}
                                className={`flex-1 py-3 text-sm font-bold rounded-xl transition-all duration-300 ${isLogin
                                    ? 'bg-white text-indigo-600 shadow-sm'
                                    : 'text-slate-400 hover:text-slate-600'
                                    }`}
                            >
                                Sign In
                            </button>
                            {canRegister && (
                                <button
                                    onClick={() => setIsLogin(false)}
                                    className={`flex-1 py-3 text-sm font-bold rounded-xl transition-all duration-300 ${!isLogin
                                        ? 'bg-white text-indigo-600 shadow-sm'
                                        : 'text-slate-400 hover:text-slate-600'
                                        }`}
                                >
                                    Register
                                </button>
                            )}
                        </div>

                        <form onSubmit={handleSubmit} className="space-y-6">
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                {/* Email */}
                                <div className={!isLogin ? "md:col-span-1" : "md:col-span-2"}>
                                    <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2">Login Email</label>
                                    <div className="relative group">
                                        <FiMail className={`absolute left-4 top-1/2 -translate-y-1/2 ${errors.email ? 'text-rose-500' : 'text-slate-400 group-focus-within:text-indigo-600'} transition-colors`} />
                                        <input
                                            type="email"
                                            name="email"
                                            value={formData.email}
                                            onChange={handleInputChange}
                                            required
                                            className={`w-full bg-slate-50 border rounded-2xl py-3.5 pl-12 pr-4 text-slate-900 focus:ring-4 focus:border-indigo-600/30 outline-none transition-all placeholder:text-slate-400 ${errors.email ? 'border-rose-500/50 focus:ring-rose-500/20' : 'border-slate-200 focus:ring-indigo-600/10'}`}
                                            placeholder="Enter your email"
                                        />
                                    </div>
                                    {errors.email && <p className="mt-1.5 text-xs text-rose-500 px-1 font-medium">{errors.email}</p>}
                                </div>

                                {/* Full Name (Signup only) */}
                                {!isLogin && (
                                    <div className="md:col-span-1">
                                        <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2">Full Name</label>
                                        <div className="relative group">
                                            <FiUser className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400 group-focus-within:text-indigo-600 transition-colors" />
                                            <input
                                                type="text"
                                                name="full_name"
                                                value={formData.full_name}
                                                onChange={handleInputChange}
                                                required
                                                className="w-full bg-slate-50 border border-slate-200 rounded-2xl py-3.5 pl-12 pr-4 text-slate-900 focus:ring-4 focus:ring-indigo-600/10 focus:border-indigo-600/30 outline-none transition-all"
                                                placeholder="Legal name"
                                            />
                                        </div>
                                    </div>
                                )}

                                {/* Password */}
                                <div className={!isLogin ? "md:col-span-1" : "md:col-span-2"}>
                                    <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2">Password</label>
                                    <div className="relative group">
                                        <FiLock className={`absolute left-4 top-1/2 -translate-y-1/2 ${errors.password ? 'text-rose-500' : 'text-slate-400 group-focus-within:text-indigo-600'} transition-colors`} />
                                        <input
                                            type={showPassword ? "text" : "password"}
                                            name="password"
                                            value={formData.password}
                                            onChange={handleInputChange}
                                            required
                                            className={`w-full bg-slate-50 border rounded-2xl py-3.5 pl-12 pr-12 text-slate-900 focus:ring-4 focus:border-indigo-600/30 outline-none transition-all placeholder:text-slate-400 ${errors.password ? 'border-rose-500/50 focus:ring-rose-500/20' : 'border-slate-200 focus:ring-indigo-600/10'}`}
                                            placeholder="••••••••"
                                        />
                                        <button
                                            type="button"
                                            onClick={() => setShowPassword(!showPassword)}
                                            className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 hover:text-indigo-600"
                                        >
                                            {showPassword ? <FiEyeOff size={18} /> : <FiEye size={18} />}
                                        </button>
                                    </div>
                                    {errors.password && <p className="mt-1.5 text-xs text-rose-500 px-1 font-medium">{errors.password}</p>}
                                </div>

                                {/* Confirm Password (Signup) */}
                                {!isLogin && (
                                    <div className="md:col-span-1">
                                        <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2">Confirm Password</label>
                                        <div className="relative group">
                                            <FiLock className={`absolute left-4 top-1/2 -translate-y-1/2 ${errors.confirmPassword ? 'text-rose-500' : 'text-slate-400 group-focus-within:text-indigo-600'} transition-colors`} />
                                            <input
                                                type={showConfirmPassword ? "text" : "password"}
                                                name="confirmPassword"
                                                value={formData.confirmPassword}
                                                onChange={handleInputChange}
                                                required
                                                className={`w-full bg-slate-50 border rounded-2xl py-3.5 pl-12 pr-12 text-slate-900 focus:ring-4 focus:border-indigo-600/30 outline-none transition-all placeholder:text-slate-400 ${errors.confirmPassword ? 'border-rose-500/50 focus:ring-rose-500/20' : 'border-slate-200 focus:ring-indigo-600/10'}`}
                                                placeholder="••••••••"
                                            />
                                            <button
                                                type="button"
                                                onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                                                className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 hover:text-indigo-600"
                                            >
                                                {showConfirmPassword ? <FiEyeOff size={18} /> : <FiEye size={18} />}
                                            </button>
                                        </div>
                                    </div>
                                )}

                                {!isLogin && (
                                    <>
                                        {/* Common Profile Fields */}
                                        <div className="md:col-span-1">
                                            <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2">Phone Number</label>
                                            <div className="relative group">
                                                <FiPhone className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" />
                                                <input
                                                    type="text"
                                                    name="phone"
                                                    value={formData.phone}
                                                    onChange={handleInputChange}
                                                    required
                                                    className="w-full bg-slate-50 border border-slate-200 rounded-2xl py-3.5 pl-12 pr-4 text-slate-900 focus:ring-4 focus:ring-indigo-600/10 focus:border-indigo-600/30 outline-none transition-all"
                                                    placeholder="+91-XXXXXXXXXX"
                                                />
                                            </div>
                                        </div>

                                        <div className="md:col-span-1">
                                            <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2">Emergency Contact</label>
                                            <div className="relative group">
                                                <FiAlertTriangle className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" />
                                                <input
                                                    type="text"
                                                    name="emergency_contact_phone"
                                                    value={formData.emergency_contact_phone}
                                                    onChange={handleInputChange}
                                                    required
                                                    className="w-full bg-slate-50 border border-slate-200 rounded-2xl py-3.5 pl-12 pr-4 text-slate-900 focus:ring-4 focus:ring-indigo-600/10 focus:border-indigo-600/30 outline-none transition-all"
                                                    placeholder="Emergency Phone"
                                                />
                                            </div>
                                        </div>

                                        {/* Driver Specific Registration */}
                                        {role === 'driver' && (
                                            <>
                                                <div className="md:col-span-1">
                                                    <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2">License ID</label>
                                                    <div className="relative group">
                                                        <FiCreditCard className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" />
                                                        <input
                                                            type="text"
                                                            name="license_number"
                                                            value={formData.license_number}
                                                            onChange={handleInputChange}
                                                            required
                                                            className="w-full bg-slate-50 border border-slate-200 rounded-2xl py-3.5 pl-12 pr-4 text-slate-900 focus:ring-4 focus:ring-indigo-600/10 focus:border-indigo-600/30 outline-none transition-all"
                                                            placeholder="AB12345"
                                                        />
                                                    </div>
                                                </div>
                                                <div className="md:col-span-1">
                                                    <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2">Vehicle Number</label>
                                                    <div className="relative group">
                                                        <FiBriefcase className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" />
                                                        <input
                                                            type="text"
                                                            name="vehicle_number"
                                                            value={formData.vehicle_number}
                                                            onChange={handleInputChange}
                                                            required
                                                            className="w-full bg-slate-50 border border-slate-200 rounded-2xl py-3.5 pl-12 pr-4 text-slate-900 focus:ring-4 focus:ring-indigo-600/10 focus:border-indigo-600/30 outline-none transition-all"
                                                            placeholder="TN 01 AB 1234"
                                                        />
                                                    </div>
                                                </div>
                                            </>
                                        )}

                                        {/* Rider Specific Registration */}
                                        {role === 'rider' && (
                                            <div className="md:col-span-1">
                                                <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2">Gender</label>
                                                <div className="relative">
                                                    <FiUser className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400 z-10" />
                                                    <select
                                                        name="gender"
                                                        value={formData.gender}
                                                        onChange={handleInputChange}
                                                        className="w-full bg-slate-50 border border-slate-200 rounded-2xl py-3.5 pl-12 pr-4 text-slate-900 outline-none focus:ring-4 focus:ring-indigo-600/10 focus:border-indigo-600/30 appearance-none"
                                                    >
                                                        <option value="female" className="bg-white">Female</option>
                                                        <option value="male" className="bg-white">Male</option>
                                                        <option value="other" className="bg-white">Other</option>
                                                    </select>
                                                </div>
                                            </div>
                                        )}

                                        {/* Terms & Conditions */}
                                        <div className="md:col-span-2 mt-2">
                                            <label className="flex items-center gap-3 cursor-pointer group">
                                                <div className="relative flex items-center">
                                                    <input
                                                        type="checkbox"
                                                        required
                                                        className="peer h-5 w-5 cursor-pointer appearance-none rounded border border-slate-200 bg-slate-50 checked:border-indigo-600 checked:bg-indigo-600 transition-all"
                                                    />
                                                    <FiCheckCircle className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-3.5 h-3.5 text-white opacity-0 peer-checked:opacity-100 transition-opacity pointer-events-none" />
                                                </div>
                                                <span className="text-sm text-slate-500 group-hover:text-slate-700 transition-colors select-none font-medium">
                                                    I agree to the <span className="text-indigo-600 hover:text-indigo-700 underline underline-offset-2">Terms of Service</span> and <span className="text-indigo-600 hover:text-indigo-700 underline underline-offset-2">Privacy Policy</span>
                                                </span>
                                            </label>
                                        </div>
                                    </>
                                )}
                            </div>

                            {/* Status and Info Messages for non-self registrable roles */}
                            {!canRegister && !isLogin && (
                                <div className="bg-amber-50 border border-amber-100 p-4 rounded-2xl flex items-start gap-3">
                                    <FiAlertTriangle className="text-amber-500 shrink-0 mt-0.5" />
                                    <p className="text-xs text-amber-600 leading-relaxed font-medium">
                                        Accounts for {role === 'dispatcher' ? 'Dispatchers' : 'Admins'} are managed by the organization.
                                        Please contact your system administrator for access.
                                    </p>
                                </div>
                            )}

                            {/* Error Reporting */}
                            {globalError && (
                                <div className={`p-4 rounded-2xl flex items-center gap-3 animate-in fade-in slide-in-from-top-2 duration-300 ${globalError.includes('successfully') ? 'bg-emerald-50 border border-emerald-100 text-emerald-600' : 'bg-rose-50 border border-rose-100 text-rose-600'}`}>
                                    {globalError.includes('successfully') ? <FiCheckCircle className="shrink-0" /> : <FiAlertTriangle className="shrink-0" />}
                                    <span className="text-sm font-bold">{globalError}</span>
                                </div>
                            )}

                            <button
                                type="submit"
                                disabled={loading || (Object.keys(errors).length > 0) || (!canRegister && !isLogin)}
                                className="w-full py-4 bg-indigo-600 hover:bg-indigo-700 text-white font-bold rounded-2xl shadow-xl shadow-indigo-600/20 transition-all active:scale-[0.98] disabled:opacity-30 disabled:grayscale disabled:cursor-not-allowed group"
                            >
                                {loading ? (
                                    <div className="flex items-center justify-center gap-2">
                                        <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                                        <span>Processing...</span>
                                    </div>
                                ) : (
                                    <div className="flex items-center justify-center gap-2">
                                        <span>{isLogin ? 'Enter Dashboard' : (role === 'driver' ? 'Submit Application' : 'Create Account')}</span>
                                        <FiShield className="group-hover:translate-x-1 transition-transform" />
                                    </div>
                                )}
                            </button>
                        </form>

                        <div className="mt-8 text-center text-xs">
                            {isLogin ? (
                                <p className="text-slate-400 font-bold">
                                    {canRegister ? (
                                        <>New to SmartShield? <span onClick={() => setIsLogin(false)} className="text-indigo-600 cursor-pointer hover:underline underline-offset-4 decoration-2">Apply Now</span></>
                                    ) : (
                                        <span className="opacity-50 italic">Restricted Access: Organizational Login Only</span>
                                    )}
                                </p>
                            ) : (
                                <p className="text-slate-400 font-bold">
                                    Already using SmartShield? <span onClick={() => setIsLogin(true)} className="text-indigo-600 cursor-pointer hover:underline underline-offset-4 decoration-2">Sign In</span>
                                </p>
                            )}
                        </div>
                    </div>
                </div>

                <p className="mt-8 text-center text-slate-400 text-[10px] font-bold uppercase tracking-[0.2em]">
                    Enterprise-Grade Safety Infrastructure &copy; 2026
                </p>
            </div>
        </div>
    );
};

export default Auth;
