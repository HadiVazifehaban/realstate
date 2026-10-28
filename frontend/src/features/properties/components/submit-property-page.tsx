'use client';

import * as React from 'react';

import { Icons } from '@/components/icons';
import { OsmLocationPicker } from '@/components/OsmLocationPicker';
import { PropertyMediaUploader } from './property-media-uploader';
import PageContainer from '@/components/layout/page-container';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Progress } from '@/components/ui/progress';
import { Textarea } from '@/components/ui/textarea';
import { cn, formatPricePerMeter, formatToman, toPersianDigits } from '@/lib/utils';
import { toast } from 'sonner';

import { useSubmitProperty, useUploadPropertyMedia } from '../hooks';
import {
  DEAL_TYPE_LABELS,
  PROPERTY_TYPE_LABELS,
  SUBMITTER_LABELS,
  formatBuildingAge
} from '../utils/labels';
import { PROPERTY_TYPES } from '../types';
import type { DealType, PropertyType } from '../types';
import { useRealmRoles } from '@/hooks/use-auth';
import { submitterKindFromRoles } from '../utils/submitter';

/** Tehran city centre -- the form starts somewhere every agent recognises. */
const DEFAULT_CENTER = { lat: 35.6892, lng: 51.389 };

/** Every deal family this form can register, in the order a broker reads them. */
const DEAL_CHOICES: { value: DealType; hint: string }[] = [
  { value: 'SALE', hint: 'قیمت کل' },
  { value: 'RENT', hint: 'ودیعه و اجارهٔ ماهانه' },
  { value: 'FULL_MORTGAGE', hint: 'فقط ودیعه' }
];

const AMENITIES = [
  { key: 'has_elevator', label: 'آسانسور', icon: 'amenityElevator' },
  { key: 'has_parking', label: 'پارکینگ', icon: 'amenityParking' },
  { key: 'has_storage', label: 'انباری', icon: 'amenityStorage' },
  { key: 'has_balcony', label: 'بالکن', icon: 'amenityBalcony' }
] as const;

type AmenityKey = (typeof AMENITIES)[number]['key'];

interface FormState {
  property_type: PropertyType;
  deal_type: DealType;
  title: string;
  description: string;
  area: number | null;
  rooms: number | null;
  floor: number | null;
  total_floors: number | null;
  year_built: number | null;
  total_price: number | null;
  deposit_amount: number | null;
  monthly_rent: number | null;
  has_elevator: boolean;
  has_parking: boolean;
  has_storage: boolean;
  has_balcony: boolean;
  owner_name: string;
  owner_phone: string;
}

const EMPTY_FORM: FormState = {
  property_type: 'APARTMENT',
  deal_type: 'SALE',
  title: '',
  description: '',
  area: null,
  rooms: null,
  floor: null,
  total_floors: null,
  year_built: null,
  total_price: null,
  deposit_amount: null,
  monthly_rent: null,
  has_elevator: false,
  has_parking: false,
  has_storage: false,
  has_balcony: false,
  owner_name: '',
  owner_phone: ''
};

/** Persian and Arabic-Indic digits are what a Persian keyboard produces. */
const DIGIT_FOLD: Record<string, string> = {
  '۰': '0', '۱': '1', '۲': '2', '۳': '3', '۴': '4',
  '۵': '5', '۶': '6', '۷': '7', '۸': '8', '۹': '9',
  '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4',
  '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9'
};

/** Keeps only ASCII digits, so «۱۲۵ متر» and «125۰» both land on 1250. */
function digitsOnly(input: string): string {
  return Array.from(input)
    .map((char) => DIGIT_FOLD[char] ?? char)
    .filter((char) => char >= '0' && char <= '9')
    .join('');
}

/** Format numeric entry for readability; year stays ungrouped. */
function fieldDigits(value: number | null, id?: string): string {
  if (value === null) return '';
  if (id === 'year_built') return toPersianDigits(String(value));
  return toPersianDigits(value.toLocaleString('en-US'));
}

/**
 * Direct registration by an owner or an advisor, on one page.
 *
 * Laid out as a form and a running summary side by side rather than as a
 * wizard: the fields a file needs are known the moment the advisor opens it,
 * and a summary that fills in as they type is what tells them what is still
 * missing -- a Next button does not.
 */
export default function SubmitPropertyPage() {
  const [coordinates, setCoordinates] = React.useState(DEFAULT_CENTER);
  const [form, setForm] = React.useState<FormState>(EMPTY_FORM);
  // Manual address line: OSM reverse-geocoding is optional; the
  // advisor types the address instead of it being auto-filled from the pin.
  const [district, setDistrict] = React.useState('');
  /** Set once the advisor actually places the pin, so the summary can say so. */
  const [pinned, setPinned] = React.useState(false);
  /** Photos/video chosen here, uploaded once the listing row exists. */
  const [mediaFiles, setMediaFiles] = React.useState<File[]>([]);
  /** The id of the listing just created, which the upload step then targets. */
  const [createdPropertyId, setCreatedPropertyId] = React.useState<string | null>(null);
  const [uploadProgress, setUploadProgress] = React.useState<number | null>(null);
  const [submissionNotice, setSubmissionNotice] = React.useState<string | null>(null);

  const submitProperty = useSubmitProperty();
  const uploadMedia = useUploadPropertyMedia(createdPropertyId);
  // Read-only: how the node will stamp this row. The server re-derives it from
  // the signed token, so this is a label, not a choice -- there is deliberately
  // no picker here, because a picker would be a lie about who is filing.
  const realmRoles = useRealmRoles();
  const submitterKind = submitterKindFromRoles(realmRoles);

  // If not logged in, show guest mode
  const isGuest = !realmRoles || realmRoles.length === 0;

  const update = <K extends keyof FormState>(key: K, value: FormState[K]) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  const handlePick = React.useCallback((lat: number, lng: number) => {
    setPinned(true);
    setCoordinates({ lat, lng });
  }, []);

  const isRent = form.deal_type !== 'SALE';
  const depositOnly = form.deal_type === 'FULL_MORTGAGE';

  // The node refuses a rent with no money against it, so the same rule is
  // applied here rather than discovered after a round trip.
  const missingRentAmount = isRent && !form.deposit_amount && !form.monthly_rent;
  const missingTitle = form.title.trim().length === 0;
  const missingSalePrice = !isRent && form.total_price === null;
  const invalidYearBuilt =
    form.year_built !== null &&
    (form.year_built < 1300 || form.year_built > new Date().getFullYear() + 1);
  const locationIsValid =
    Number.isFinite(coordinates.lat) && Number.isFinite(coordinates.lng) &&
    coordinates.lat >= 25 && coordinates.lat <= 40.5 &&
    coordinates.lng >= 44 && coordinates.lng <= 64.5;
  const canSubmit =
    locationIsValid &&
    !missingRentAmount &&
    !missingSalePrice &&
    !missingTitle &&
    !invalidYearBuilt &&
    !submitProperty.isPending;

  /**
   * Register the listing, then attach whatever media was picked.
   *
   * Two steps on purpose: media attach to a row that exists, and the node takes
   * the whole batch in one multipart request. A media failure leaves the
   * listing registered and says so, instead of pretending the submit failed.
   */
  React.useEffect(() => {
    if (!createdPropertyId || mediaFiles.length === 0) return;
    let cancelled = false;
    setUploadProgress(0);
    uploadMedia.mutate(mediaFiles, {
      onSuccess: () => {
        if (cancelled) return;
        setUploadProgress(100);
        toast.success('عکس‌ها و ویدیوهای ملک ذخیره شد.');
        setMediaFiles([]);
      },
      onError: (error: Error) => {
        if (cancelled) return;
        toast.error(error.message || 'آپلود فایل‌ها ناموفق بود؛ ملک ثبت شده است.');
      },
      onSettled: () => {
        if (!cancelled) setUploadProgress(null);
      }
    });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [createdPropertyId]);

  /** Live price per metre -- the number every broker compares units by. */
  const pricePerMeter =
    !isRent && form.total_price && form.area && form.area > 0
      ? Math.round(form.total_price / form.area)
      : null;

  const checks = [
    { label: 'پین روی نقشه', done: pinned },
    { label: 'عنوان آگهی', done: !missingTitle },
    { label: 'متراژ', done: !!form.area },
    { label: isRent ? 'مبلغ ودیعه یا اجاره' : 'قیمت کل', done: !missingRentAmount && (isRent ? true : !!form.total_price) },
    { label: 'شمارهٔ تماس مالک', done: form.owner_phone.trim().length >= 8 },
    { label: 'توضیحات', done: form.description.trim().length >= 10 }
  ];
  const doneCount = checks.filter((check) => check.done).length;
  const completeness = Math.round((doneCount / checks.length) * 100);

  const reset = () => {
    setForm(EMPTY_FORM);
    setCoordinates(DEFAULT_CENTER);
    setDistrict('');
    setPinned(false);
  };

  const handleSubmit = () => {
    if (!canSubmit) return;
    setSubmissionNotice(null);
    submitProperty.mutate({
      latitude: coordinates.lat,
      longitude: coordinates.lng,
      district: district.trim() || null,
      property_type: form.property_type,
      deal_type: form.deal_type,
      title: form.title.trim(),
      description: form.description,
      area: form.area,
      rooms: form.rooms,
      floor: form.floor,
      total_floors: form.total_floors,
      year_built: form.year_built,
      // A sale carries no deposit, a rent carries no sale price, and a full
      // mortgage carries no monthly rent: sending the wrong one leaves a figure
      // on the record that the deal cannot have.
      total_price: isRent ? null : form.total_price,
      deposit_amount: isRent ? form.deposit_amount : null,
      monthly_rent: depositOnly ? null : isRent ? form.monthly_rent : null,
      has_elevator: form.has_elevator,
      has_parking: form.has_parking,
      has_storage: form.has_storage,
      has_balcony: form.has_balcony,
      owner_name: form.owner_name.trim() || null,
      owner_phone: form.owner_phone.trim() || null
    }, {
      onSuccess: (result) => {
        const message = result.created
          ? 'ملک با موفقیت ثبت شد.'
          : 'ملک با آگهی موجود تطبیق داده شد و اطلاعات آن به‌روزرسانی شد.';
        setSubmissionNotice(message);
        setCreatedPropertyId(result.property_id);
      },
      onError: (error: Error) => {
        setSubmissionNotice(error.message || 'ثبت ملک ناموفق بود. موارد فرم را بررسی کنید و دوباره تلاش کنید.');
      }
    });
  };

  return (
    <PageContainer
      pageTitle='ثبت ملک'
      pageDescription='ثبت مستقیم توسط مالک یا مشاور — مشخصات، قیمت و راه ارتباطی در یک فرم.'
    >
      <div className='min-w-0 w-full overflow-x-hidden'>
      {/* Who the row will be stamped as. Read-only on purpose: the class of
          party comes from the signed token, so this tells the filer what the
          node will record rather than letting them choose. Without it, the
          «ثبت ملک» / «ثبت دفتر» badge on the finished listing is a surprise. */}
      <div className='mb-4 flex flex-wrap items-center gap-2 rounded-xl border border-border bg-muted/30 px-3 py-2'>
        <span className='text-muted-foreground text-xs'>این ملک ثبت می‌شود به‌نام:</span>
        {isGuest ? (
          <Badge variant='outline'>
            مهمان (ثبت تستی)
          </Badge>
        ) : submitterKind ? (
          <Badge variant={submitterKind === 'PERSON' ? 'default' : 'secondary'}>
            {SUBMITTER_LABELS[submitterKind]}
          </Badge>
        ) : (
          <span className='text-destructive text-xs'>
            نقش حساب شما اجازهٔ ثبت ملک را نمی‌دهد.
          </span>
        )}
      </div>
      <div className='grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_21rem]'>
        <div className='space-y-5'>
          {/* ---- نوع معامله drives every price field below it. ---- */}
          <Card className='border-gold-accent/25 overflow-hidden'>
            <CardContent className='pt-6'>
              <SectionTitle index='۱' title='نوع معامله' hint='جای مبلغ‌ها را همین تعیین می‌کند.' />
              <div className='mt-4 grid gap-2 sm:grid-cols-3'>
                {DEAL_CHOICES.map((choice) => {
                  const active = form.deal_type === choice.value;
                  return (
                    <button
                      key={choice.value}
                      type='button'
                      aria-pressed={active}
                      onClick={() => update('deal_type', choice.value)}
                      className={cn(
                        'flex flex-col items-start gap-1 rounded-xl border p-3 text-start transition-all',
                        active
                          ? 'border-gold-accent/60 bg-gold-accent/15 shadow-[0_0_18px_rgba(229,168,123,0.18)]'
                          : 'border-border hover:border-gold-accent/40 hover:bg-muted/40'
                      )}
                    >
                      <span className='flex w-full items-center justify-between'>
                        <span className='text-sm font-semibold'>
                          {DEAL_TYPE_LABELS[choice.value]}
                        </span>
                        <Icons.check
                          aria-hidden
                          className={cn(
                            'size-4',
                            active ? 'text-gold-dark opacity-100' : 'opacity-0'
                          )}
                        />
                      </span>
                      <span className='text-muted-foreground text-xs'>{choice.hint}</span>
                    </button>
                  );
                })}
              </div>
            </CardContent>
          </Card>

          {/* ---- موقعیت: the picker owns the pin, the coordinates and the address. ---- */}
          <Card>
            <CardHeader>
              <CardTitle className='text-base'>
                <SectionTitle index='۲' title='موقعیت ملک' hint='پین را جابه‌جا کنید؛ آدرس و محله خودکار پر می‌شود.' />
              </CardTitle>
            </CardHeader>
            <CardContent>
              {/* OSM location picker: pin on the map, GPS auto-pin, or type coordinates. */}
              <OsmLocationPicker
                value={coordinates}
                onChange={handlePick}
              />

              <div className='mt-3 space-y-2'>
                <Label htmlFor='manual-district'>آدرس / محله (دستی)</Label>
                <Input
                  id='manual-district'
                  value={district}
                  onChange={(event) => setDistrict(event.target.value)}
                  placeholder='مثلاً سعادت‌آباد، خیابان …'
                />
              </div>
            </CardContent>
          </Card>

          {/* ---- مشخصات ---- */}
          <Card>
            <CardHeader>
              <CardTitle className='text-base'>
                <SectionTitle index='۳' title='مشخصات ملک' hint='کالبد و فنی واحد را کامل کنید.' />
              </CardTitle>
            </CardHeader>
            <CardContent className='space-y-5'>
              <div className='space-y-2'>
                <Label>نوع ملک</Label>
                <div className='grid grid-cols-2 gap-2 sm:grid-cols-4'>
                  {PROPERTY_TYPES.map((type) => {
                    const active = form.property_type === type;
                    return (
                      <button
                        key={type}
                        type='button'
                        aria-pressed={active}
                        onClick={() => update('property_type', type)}
                        className={cn(
                          'rounded-lg border px-3 py-2 text-xs font-medium transition-all',
                          active
                            ? 'border-gold-accent/60 bg-gold-accent/15 text-gold-dark'
                            : 'border-border text-muted-foreground hover:border-gold-accent/40 hover:text-foreground'
                        )}
                      >
                        {PROPERTY_TYPE_LABELS[type]}
                      </button>
                    );
                  })}
                </div>
              </div>

              <div className='grid gap-4 sm:grid-cols-2 lg:grid-cols-3'>
                <NumberField
                  id='area'
                  label='متراژ'
                  value={form.area}
                  min={1}
                  max={100000}
                  onChange={(value) => update('area', value)}
                />
                <NumberField
                  id='rooms'
                  label='تعداد خواب'
                  value={form.rooms}
                  min={0}
                  max={30}
                  onChange={(value) => update('rooms', value)}
                />
                <NumberField
                  id='floor'
                  label='طبقه'
                  value={form.floor}
                  min={-5}
                  max={100}
                  onChange={(value) => update('floor', value)}
                />
                <NumberField
                  id='total_floors'
                  label='تعداد کل طبقات'
                  value={form.total_floors}
                  min={0}
                  max={100}
                  onChange={(value) => update('total_floors', value)}
                />
                <NumberField
                  id='year_built'
                  label='سال ساخت'
                  value={form.year_built}
                  min={1300}
                  max={new Date().getFullYear() + 1}
                  hint={formatBuildingAge(form.year_built)}
                  onChange={(value) => update('year_built', value)}
                />
              </div>

              <div className='space-y-3'>
                <Label>امکانات</Label>
                <div className='flex flex-wrap gap-2'>
                  {AMENITIES.map((amenity) => {
                    const Icon = Icons[amenity.icon];
                    const active = form[amenity.key as AmenityKey] as boolean;
                    return (
                      <button
                        key={amenity.key}
                        type='button'
                        aria-pressed={active}
                        onClick={() => update(amenity.key as AmenityKey, !active)}
                        className={cn(
                          'flex items-center gap-2 rounded-full border px-3 py-2 text-xs font-medium transition-all',
                          active
                            ? 'border-gold-accent/60 bg-gold-accent/15 text-gold-dark'
                            : 'border-border text-muted-foreground hover:border-gold-accent/40 hover:text-foreground'
                        )}
                      >
                        <Icon aria-hidden className='size-4' />
                        {amenity.label}
                        {active && <Icons.check aria-hidden className='size-3.5' />}
                      </button>
                    );
                  })}
                </div>
              </div>

              <div className='grid gap-4'>
                <div className='space-y-2'>
                  <Label htmlFor='title'>عنوان آگهی</Label>
                  <Input
                    id='title'
                    value={form.title}
                    onChange={(event) => update('title', event.target.value)}
                    placeholder='آپارتمان ۱۲۰ متری سعادت‌آباد، بازسازی‌شده'
                  />
                  {missingTitle && (
                    <p className='text-muted-foreground text-xs'>
                      عنوان، همان چیزی است که دفتر بعداً فایل را با آن پیدا می‌کند.
                    </p>
                  )}
                </div>

                <div className='space-y-2'>
                  <Label htmlFor='description'>توضیحات</Label>
                  <Textarea
                    id='description'
                    rows={4}
                    value={form.description}
                    onChange={(event) => update('description', event.target.value)}
                    placeholder='نور، بازسازی، وضعیت سند، دسترسی‌ها، همسایگی.'
                  />
                </div>
              </div>
            </CardContent>
          </Card>

          {/* ---- قیمت و تماس ---- */}
          <Card>
            <CardHeader>
              <CardTitle className='text-base'>
                <SectionTitle index='۴' title='قیمت و راه ارتباطی' hint='شمارهٔ مالک رمزنگاری‌شده ذخیره می‌شود.' />
              </CardTitle>
            </CardHeader>
            <CardContent className='space-y-5'>
              <div className='grid gap-4 sm:grid-cols-2'>
                {!isRent && (
                  <MoneyField
                    id='total_price'
                    label='قیمت کل (تومان)'
                    value={form.total_price}
                    onChange={(value) => update('total_price', value)}
                  />
                )}

                {isRent && (
                  <MoneyField
                    id='deposit_amount'
                    label='ودیعه (تومان)'
                    value={form.deposit_amount}
                    onChange={(value) => update('deposit_amount', value)}
                  />
                )}

                {isRent && !depositOnly && (
                  <MoneyField
                    id='monthly_rent'
                    label='اجارهٔ ماهانه (تومان)'
                    value={form.monthly_rent}
                    onChange={(value) => update('monthly_rent', value)}
                  />
                )}

                {pricePerMeter !== null && (
                  <div className='border-gold-accent/30 bg-gold-accent/5 flex flex-col justify-center gap-1 rounded-xl border p-3'>
                    <span className='text-muted-foreground text-xs'>قیمت هر متر (محاسبه‌شده)</span>
                    <span className='text-gold-dark text-sm font-semibold tabular-nums'>
                      {formatPricePerMeter(pricePerMeter)}
                    </span>
                  </div>
                )}

                <div className='space-y-2'>
                  <Label htmlFor='owner_name'>نام مالک</Label>
                  <Input
                    id='owner_name'
                    value={form.owner_name}
                    onChange={(event) => update('owner_name', event.target.value)}
                  />
                  {/* Who is actually on the deed is its own question. A broker
                      filing a client's unit is «بنگاه» while these two fields
                      stay the owner's, so the labels never claim the filer and
                      the owner are the same party. */}
                  <p className='text-muted-foreground text-xs'>
                    {submitterKind === 'AGENCY'
                      ? 'نام و شمارهٔ مالک ملک را وارد کنید؛ این اطلاعات به‌نام بنگاه شما ثبت می‌شود و رمزنگاری می‌گردد.'
                      : 'اطلاعات تماس شما به‌صورت رمزنگاری‌شده ذخیره می‌شود و در آگهی نمایش داده نمی‌شود.'}
                  </p>
                </div>

                <div className='space-y-2'>
                  <Label htmlFor='owner_phone'>شمارهٔ تماس مالک</Label>
                  <Input
                    id='owner_phone'
                    inputMode='tel'
                    dir='ltr'
                    value={form.owner_phone}
                    onChange={(event) => update('owner_phone', event.target.value)}
                  />
                </div>
              </div>

              {missingRentAmount && (
                <p className='text-destructive text-xs'>
                  {depositOnly
                    ? 'برای رهن کامل، مبلغ ودیعه الزامی است.'
                    : 'برای آگهی رهن و اجاره، مبلغ ودیعه یا اجارهٔ ماهانه الزامی است.'}
                </p>
              )}
            </CardContent>
          </Card>

          {/* ---- Media: the listing's photos and walkthrough video. ----
              Held here and uploaded after the listing exists, because media
              attach to a row that has an id. */}
          <Card className='border-gold-accent/25 overflow-hidden'>
            <CardContent className='pt-6'>
              <SectionTitle
                index='۶'
                title='عکس و ویدیو'
                hint='عکس‌ها بعد از ثبت ملک روی همین نود ذخیره می‌شوند.'
              />
              <div className='mt-4'>
                <PropertyMediaUploader
                  files={mediaFiles}
                  onChange={setMediaFiles}
                  disabled={submitProperty.isPending || uploadMedia.isPending}
                  progress={uploadProgress}
                />
              </div>
            </CardContent>
          </Card>
        </div>

        {/* ---- Running summary: what is filled, what is missing, what it costs. ---- */}
        <aside className='space-y-4 lg:sticky lg:top-4'>
          <Card className='border-gold-accent/25'>
            <CardHeader>
              <CardTitle className='text-base'>خلاصهٔ ثبت</CardTitle>
              <CardDescription>با هر فیلد، این کارت به‌روز می‌شود.</CardDescription>
            </CardHeader>
            <CardContent className='space-y-4'>
              {/* The percentage is written here rather than left to the
                  primitive's own value: it prints «0%» with Latin digits, on a
                  page whose every other number is Persian. */}
              <Progress value={completeness} className='flex-col gap-2'>
                <div className='flex w-full items-center justify-between text-xs'>
                  <span className='text-muted-foreground'>آمادگی ثبت</span>
                  <span className='text-foreground font-semibold tabular-nums'>
                    {toPersianDigits(String(completeness))}٪
                  </span>
                </div>
              </Progress>

              <ul className='space-y-2'>
                {checks.map((check) => (
                  <li key={check.label} className='flex items-center gap-2 text-xs'>
                    {check.done ? (
                      <Icons.circleCheck
                        aria-hidden
                        className='text-gold-dark size-4 shrink-0'
                      />
                    ) : (
                      <Icons.circle aria-hidden className='text-muted-foreground size-4 shrink-0' />
                    )}
                    <span className={cn(check.done ? '' : 'text-muted-foreground')}>
                      {check.label}
                    </span>
                  </li>
                ))}
              </ul>

              <dl className='border-border space-y-2 border-t pt-3 text-xs'>
                <SummaryRow label='نوع معامله' value={DEAL_TYPE_LABELS[form.deal_type]} />
                <SummaryRow label='نوع ملک' value={PROPERTY_TYPE_LABELS[form.property_type]} />
                {form.area && (
                  <SummaryRow
                    label='متراژ'
                    value={`${toPersianDigits(Math.round(form.area).toLocaleString('en-US'))} متر مربع`}
                  />
                )}
                {!isRent && form.total_price && (
                  <SummaryRow label='قیمت کل' value={formatToman(form.total_price)} />
                )}
                {isRent && form.deposit_amount && (
                  <SummaryRow label='ودیعه' value={formatToman(form.deposit_amount)} />
                )}
                {isRent && !depositOnly && form.monthly_rent && (
                  <SummaryRow label='اجارهٔ ماهانه' value={formatToman(form.monthly_rent)} />
                )}
                {pricePerMeter !== null && (
                  <SummaryRow label='قیمت هر متر' value={formatPricePerMeter(pricePerMeter)} />
                )}
                {district && <SummaryRow label='آدرس' value={district} />}
              </dl>

              <div className='flex flex-col gap-2'>
                {submissionNotice && (
                  <p
                    role={submitProperty.isError ? 'alert' : 'status'}
                    className={cn(
                      'rounded-lg border px-3 py-2 text-sm leading-6',
                      submitProperty.isError
                        ? 'border-destructive/40 bg-destructive/5 text-destructive'
                        : 'border-gold-accent/40 bg-gold-accent/10 text-foreground'
                    )}
                  >
                    {submissionNotice}
                  </p>
                )}
                <Button onClick={handleSubmit} disabled={!canSubmit} aria-label='ثبت ملک در دفتر' className='w-full'>
                  {submitProperty.isPending ? 'در حال ثبت…' : 'ثبت ملک در دفتر'}
                </Button>
                <Button
                  variant='ghost'
                  onClick={reset}
                  disabled={submitProperty.isPending}
                  aria-label='پاک کردن فرم'
                  className='w-full'
                >
                  پاک کردن فرم
                </Button>
              </div>

              {!canSubmit && !submitProperty.isPending && (
                <p className='text-muted-foreground text-center text-xs'>
                  {!locationIsValid
                    ? 'موقعیت انتخاب‌شده خارج از محدودهٔ پشتیبانی است؛ پین را در محدودهٔ ایران قرار دهید.'
                    : invalidYearBuilt
                      ? 'سال ساخت را به‌صورت سال میلادی بین ۱۳۰۰ تا سال آینده وارد کنید.'
                      : missingTitle
                        ? 'برای ثبت، عنوان آگهی را وارد کنید.'
                        : missingSalePrice
                          ? 'برای ثبت آگهی فروش، قیمت کل را وارد کنید.'
                          : missingRentAmount
                            ? 'برای ثبت آگهی اجاره، ودیعه یا اجارهٔ ماهانه را وارد کنید.'
                            : 'در حال ثبت آگهی…'}
                </p>
              )}
            </CardContent>
          </Card>
        </aside>
      </div>
      </div>
    </PageContainer>
  );
}

/** Numbered section heading: a gold chip, a title and a one-line hint. */
function SectionTitle({ index, title, hint }: { index: string; title: string; hint?: string }) {
  return (
    <span className='flex items-start gap-3'>
      <span className='border-gold-accent/40 bg-gold-accent/10 text-gold-dark flex size-7 shrink-0 items-center justify-center rounded-lg border text-xs font-bold'>
        {index}
      </span>
      <span className='flex flex-col gap-0.5'>
        <span className='text-sm font-semibold'>{title}</span>
        {hint && <span className='text-muted-foreground text-xs font-normal'>{hint}</span>}
      </span>
    </span>
  );
}

function SummaryRow({ label, value }: { label: string; value: string }) {
  return (
    <div className='flex items-start justify-between gap-3'>
      <dt className='text-muted-foreground shrink-0'>{label}</dt>
      <dd className='truncate text-end font-medium tabular-nums'>{value}</dd>
    </div>
  );
}

/**
 * Digits-only input with a unit chip.
 *
 * A Persian keyboard types ۱-۹, so the value is folded to ASCII on the way in --
 * a `type='number'` input silently discards those keystrokes and the field looks
 * broken. Grouping is not written back into the field (that would move the caret
 * mid-edit); the amount in words sits underneath instead.
 */
function NumberField({
  id,
  label,
  hint,
  value,
  min,
  max,
  onChange
}: {
  id: string;
  label: string;
  hint?: string | null;
  value: number | null;
  min?: number;
  max?: number;
  onChange: (value: number | null) => void;
}) {
  return (
    <div className='space-y-2'>
      <Label htmlFor={id}>{label}</Label>
      <div className='relative'>
        <Input
          id={id}
          inputMode='numeric'
          dir='ltr'
          className='tabular-nums'
          value={fieldDigits(value, id)}
          onChange={(event) => {
            const digits = digitsOnly(event.target.value);
            if (digits === '') return onChange(null);
            const parsed = Number(digits);
            if (Number.isNaN(parsed)) return onChange(null);
            if (max !== undefined && parsed > max) {
              if (id !== 'year_built') return;
              onChange(parsed);
              return;
            }
            if (min !== undefined && min > 0 && parsed < min && id !== 'year_built') return;
            onChange(parsed);
          }}
        />
      </div>
      {hint && <p className='text-muted-foreground text-xs'>{hint}</p>}
    </div>
  );
}

/** Money field: digits in, the amount spelled out underneath. */
function MoneyField({
  id,
  label,
  value,
  onChange
}: {
  id: string;
  label: string;
  value: number | null;
  onChange: (value: number | null) => void;
}) {
  return (
    <div className='space-y-2'>
      <Label htmlFor={id}>{label}</Label>
      <div className='relative'>
        <Input
          id={id}
          inputMode='numeric'
          dir='ltr'
          className='tabular-nums'
          value={fieldDigits(value)}
          onChange={(event) => {
            const digits = digitsOnly(event.target.value).slice(0, 15);
            const next = digits === '' ? null : Number(digits);
            if (next === null || next <= 9_000_000_000_000_000) onChange(next);
          }}
        />
      </div>
      {value !== null && value > 0 && (
        <p className='text-gold-dark text-xs font-medium'>{formatToman(value)}</p>
      )}
    </div>
  );
}
